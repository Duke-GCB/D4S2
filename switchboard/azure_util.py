import os
import json
import traceback
import subprocess
from d4s2_api.utils import MessageFactory, MessageDirection
import urllib.parse
from switchboard.userservice import get_user_for_netid
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
from azure.core.exceptions import ResourceNotFoundError
from msgraph.core import GraphClient
from d4s2_api.models import AzDelivery, State, AzObjectManifest, AzDeliveryError, AzContainerPath, AzTransferStates, \
    AzStorageConfig, StorageTypes
from background_task import background
from django.conf import settings
from django.contrib.auth.models import User
from django.core.signing import Signer
from rest_framework.exceptions import ValidationError


AZURE_SERVICE_NAME = 'Azure Blob Storage'
DESTINATION_ALREADY_EXISTS_MSG = "Error: The transfer destination directory '{}' already exists."


class AzNotRecipientException(Exception):
    pass


class AzDestinationProjectAlreadyExists(Exception):
    pass


def get_credential():
    return DefaultAzureCredential()


def get_netid_for_django_user(user):
    if user.username.endswith(settings.USERNAME_EMAIL_HOST):
        return user.username.split("@")[0]
    return None


def get_details_from_container_url(container_url):
    split_result = urllib.parse.urlsplit(container_url)
    storage_account = split_result.netloc.split(".")[0]
    file_system_name = split_result.path.replace("/", "")
    return storage_account, file_system_name


def make_acl(user_id, permissions=None, apply_default=True):
    if permissions:
        acl = f"user:{user_id}:{permissions}"
    else:
        acl = f"user:{user_id}"
    if apply_default:
        return f"{acl},default:{acl}"
    else:
        return acl


class AzDataLakeProject(object):
    def __init__(self, container_url, path):
        storage_account, file_system_name = get_details_from_container_url(container_url)
        self.container_url = container_url
        self.path = path
        self.storage_account = storage_account
        self.file_system_name = file_system_name
        storage_config = AzStorageConfig.objects.get(storage_account=storage_account, container_name=file_system_name)
        self.service = DataLakeServiceClient(f"https://{storage_account}.dfs.core.windows.net/",
                                             credential=storage_config.storage_account_key)
        self.directory_client = self.service.get_directory_client(file_system_name, path)

    def exists(self):
        return self.directory_client.exists()

    def ensure_parent_directory(self):
        parent_directory_path = os.path.dirname(self.path)
        directory_client = self.service.get_directory_client(self.file_system_name, parent_directory_path)
        if not directory_client.exists():
            directory_client.create_directory()

    def move(self, destination_container_url, destination_path):
        if destination_container_url == self.container_url:
            # Within the same container simply rename the directory
            filesystem_name = "{}/{}".format(self.file_system_name, destination_path)
            self.directory_client.rename_directory(filesystem_name)
        else:
            # Copy to the destination
            from_url = "{}/{}".format(self.container_url, self.path)
            to_url = "{}/{}".format(destination_container_url,destination_path)
            copy_command = [settings.AZCOPY_COMMAND, "copy",  '--recursive', from_url, to_url]
            subprocess.run(copy_command, check=True)

            # Delete our copy
            self.directory_client.delete_directory()

    def get_file_system_client(self):
        return self.service.get_file_system_client(self.file_system_name)

    def get_paths(self):
        file_system_client = self.get_file_system_client()
        return file_system_client.get_paths(self.path)

    def get_file_manifest(self):
        file_system_client = self.get_file_system_client()
        results = []
        for file_metadata in file_system_client.get_paths(self.path):
            if file_metadata.is_directory:
                results.append(file_metadata)
            else:
                file_client = file_system_client.get_file_client(file_metadata.name)
                file_properties = dict(file_client.get_file_properties())
                del file_properties['lease']
                # Fix nested content settings
                content_settings = file_properties["content_settings"]
                file_properties["content_settings"] = {
                    "content_type": content_settings["content_type"],
                    "content_md5": content_settings["content_md5"].hex(),
                }
                results.append(file_properties)
        return results

    def add_download_user(self, azure_user_id):
        file_system_client = self.service.get_file_system_client(self.file_system_name)
        acl = make_acl(azure_user_id, permissions='r-x')
        directory_client = file_system_client.get_directory_client(self.path)
        directory_client.update_access_control_recursive(acl=acl)

    def set_owner(self, azure_user_id):
        file_paths = [self.path]
        file_system_client = self.service.get_file_system_client(self.file_system_name)
        for file_metadata in file_system_client.get_paths(self.path):
            file_paths.append(file_metadata.name)
        for file_path in file_paths:
            file_client = file_system_client.get_file_client(file_path)
            file_client.set_access_control(owner=azure_user_id)


def project_exists(container_url, path):
    project = AzDataLakeProject(container_url, path)
    return project.exists()


class AzUsers(object):
    def __init__(self, credential):
        self.graph_client = GraphClient(credential=credential)

    def get_azure_user_id(self, netid):
        username = '{}@{}'.format(netid, settings.USERNAME_EMAIL_HOST)
        response = self.graph_client.get('/users/' + username)
        response.raise_for_status()
        return response.json()["id"]


class AzDeliveryDetails(object):
    def __init__(self, delivery, user):
        self.storage = StorageTypes.AZURE
        self.delivery = delivery
        self.email_template_set = delivery.email_template_set
        self.user = user

    def get_from_user(self):
        return get_user_for_netid(self.delivery.from_netid)

    def get_to_user(self):
        return get_user_for_netid(self.delivery.to_netid)

    def get_context(self):
        from_user = self.get_from_user()
        to_user = self.get_to_user()
        return {
            'service_name': AZURE_SERVICE_NAME,
            'transfer_id': self.delivery.transfer_id,
            'from_name': from_user.full_name,
            'from_email': from_user.email,
            'from_netid': from_user.username,
            'to_name': to_user.full_name,
            'to_email': to_user.email,
            'to_netid': to_user.username,
            'project_title': self.delivery.get_simple_project_name(),
            'project_url': self.delivery.make_project_url()
        }

    def get_email_context(self, accept_url, process_type, reason, warning_message):
        from_user = self.get_from_user()
        to_user = self.get_to_user()

        return {
            'service_name': AZURE_SERVICE_NAME,
            'project_name': self.delivery.get_simple_project_name(),
            'sender_email': from_user.email,
            'sender_name': from_user.full_name,
            'sender_netid': from_user.username,
            'recipient_name': to_user.full_name,
            'recipient_email': to_user.email,
            'recipient_netid': to_user.username,
            'project_url': self.delivery.make_project_url(),
            'accept_url': accept_url,
            'type': process_type,
            'message': reason,
            'user_message': self.delivery.user_message,
            'warning_message': warning_message,
        }

    def decline_delivery(self, reason):
        # Nothing needs to be done in Azure when declining a delivery
        pass


class AzMessageFactory(MessageFactory):
    def __init__(self, delivery, user):
        super(AzMessageFactory, self).__init__(AzDeliveryDetails(delivery, user), user)


class AzDeliveryType:
    name = StorageTypes.AZURE
    delivery_cls = AzDelivery
    transfer_in_background = True

    @staticmethod
    def get_delivery(transfer_id):
        return AzDelivery.objects.get(pk=transfer_id)

    @staticmethod
    def make_delivery_details(delivery, user):
        AzDeliveryType.verify_user_is_recipient(delivery, user)
        return AzDeliveryDetails(delivery, user)

    @staticmethod
    def make_delivery_util(delivery, user):
        AzDeliveryType.verify_user_is_recipient(delivery, user)
        return AzDeliveryDetails(delivery, user)

    @staticmethod
    def transfer_delivery(delivery, user):
        AzDeliveryType.verify_user_is_recipient(delivery, user)
        # Update destination based on source container_url if not already set
        if not delivery.destination_project:
            path = "{}/{}".format(delivery.to_netid, delivery.get_simple_project_name())
            container_url = delivery.source_project.container_url
            delivery.destination_project = AzContainerPath.objects.create(path=path, container_url=container_url)
        if project_exists(delivery.destination_project.container_url, delivery.destination_project.path):
            msg = DESTINATION_ALREADY_EXISTS_MSG.format(delivery.destination_project.path)
            raise AzDestinationProjectAlreadyExists(msg)
        delivery.mark_transferring()
        TransferFunctions.transfer_delivery(delivery.id)

    @staticmethod
    def make_processed_message(delivery, user, process_type, direction, warning_message=''):
        message_factory = AzMessageFactory(delivery, user)
        return message_factory.make_processed_message(process_type, direction, warning_message=warning_message)

    @staticmethod
    def verify_user_is_recipient(delivery, user):
        if delivery.to_netid != get_netid_for_django_user(user):
            raise AzNotRecipientException()


class TransferFunctions(object):
    @staticmethod
    @background
    def transfer_delivery(delivery_id, transfer_project=True, add_download_users=True, change_owner=True,
                          email_sender=True, email_recipient=True):
        transfer = AzureTransfer(delivery_id, get_credential())
        try:
            transfer.ensure_transferring_state()
            if transfer_project:
                transfer.record_object_manifest()
                transfer.transfer_project()
            if add_download_users:
                transfer.give_download_users_permissions()
            if change_owner:
                transfer.update_owner_permissions()
            if email_sender:
                transfer.email_sender()
            if email_recipient:
                transfer.email_recipient()
            transfer.mark_complete()
        except Exception as e:
            transfer.set_failed_and_record_exception(e)
            print(f"Transfer {delivery_id} failed.")
            print(str(e))

    @staticmethod
    def restart_transfer(delivery_id):
        delivery = AzDelivery.objects.get(pk=delivery_id)
        if delivery.state != State.TRANSFERRING:
            print("Delivery {} is not in transferring state.".format((delivery.id)))
        else:
            transfer_project = delivery.transfer_state < AzTransferStates.TRANSFERRED_PROJECT
            add_download_users = delivery.transfer_state < AzTransferStates.ADDED_DOWNLOAD_USERS
            change_owner = delivery.transfer_state < AzTransferStates.CHANGED_OWNER
            email_sender = delivery.transfer_state < AzTransferStates.EMAILED_SENDER
            email_recipient = delivery.transfer_state < AzTransferStates.EMAILED_RECIPIENT
            TransferFunctions.transfer_delivery(
                delivery_id,
                transfer_project=transfer_project,
                add_download_users=add_download_users,
                change_owner=change_owner,
                email_sender=email_sender,
                email_recipient=email_recipient,
            )


class AzureTransfer(object):
    def __init__(self, delivery_id, credential):
        self.delivery = AzDelivery.objects.get(pk=delivery_id)
        delivery_source_project = self.delivery.source_project
        self.source_project = AzDataLakeProject(delivery_source_project.container_url, delivery_source_project.path)
        destination_project = self.delivery.destination_project
        self.destination_project = AzDataLakeProject(destination_project.container_url, destination_project.path)
        self.azure_users = AzUsers(credential)

    def ensure_transferring_state(self):
        if self.delivery.state != State.TRANSFERRING:
            self.delivery.mark_transferring()

    def record_object_manifest(self):
        file_data = self.source_project.get_file_manifest()
        signer = Signer()
        signed_manifest_str = signer.sign(json.dumps(file_data, default=str))
        manifest = AzObjectManifest.objects.create(content=signed_manifest_str)
        self.delivery.manifest = manifest
        self.delivery.transfer_state = AzTransferStates.CREATED_MANIFEST
        self.delivery.save()
        print("Recorded object manifest for {}.".format(self.source_project.path))

    def transfer_project(self):
        print("Beginning project transfer for {} to {}.".format(self.source_project.path, self.destination_project.path))
        self.destination_project.ensure_parent_directory()
        self.source_project.move(self.destination_project.container_url, self.destination_project.path)
        print("Project transfer complete for {} to {}.".format(self.source_project.path, self.destination_project.path))
        self.delivery.transfer_state = AzTransferStates.TRANSFERRED_PROJECT
        self.delivery.save()

    def give_download_users_permissions(self):
        netids = [self.delivery.from_netid]
        netids.extend(self.delivery.share_user_ids)
        for netid in netids:
            print("Granting download permission for user {}".format(netid))
            azure_user_id = self.azure_users.get_azure_user_id(netid)
            self.destination_project.add_download_user(azure_user_id)
        self.delivery.transfer_state = AzTransferStates.ADDED_DOWNLOAD_USERS
        self.delivery.save()

    def update_owner_permissions(self):
        print("Updating owner permissions for {}.".format(self.delivery.id))
        # This might not be necessary depending on how the bucket storage rules are created
        azure_user_id = self.azure_users.get_azure_user_id(self.delivery.to_netid)
        self.destination_project.set_owner(azure_user_id)
        self.delivery.transfer_state = AzTransferStates.CHANGED_OWNER
        self.delivery.save()

    def email_sender(self, warning_message=''):
        print("Notifying sender delivery {} has been accepted.".format(self.delivery.id))
        message = self.make_processed_message('accepted', warning_message, direction=MessageDirection.ToSender)
        message.send()
        self.delivery.transfer_state = AzTransferStates.EMAILED_SENDER
        self.delivery.sender_completion_email_text = message.email_text
        self.delivery.save()

    def email_recipient(self, warning_message=""):
        print("Notifying receiver transfer of delivery {} is complete.".format(self.delivery.id))
        message = self.make_processed_message('accepted_recipient', warning_message,
                                              direction=MessageDirection.ToRecipient)
        message.send()
        self.delivery.transfer_state = AzTransferStates.EMAILED_RECIPIENT
        self.delivery.recipient_completion_email_text = message.email_text
        self.delivery.save()

    def make_processed_message(self, process_type, warning_message, direction):
        username = '{}@{}'.format(self.delivery.from_netid, settings.USERNAME_EMAIL_HOST)
        from_user = User.objects.get(username=username)
        message_factory = AzMessageFactory(self.delivery, from_user)
        return message_factory.make_processed_message(process_type, direction, warning_message=warning_message)

    def mark_complete(self):
        print("Marking delivery {} complete.".format(self.delivery.id))
        self.delivery.state = State.ACCEPTED
        self.delivery.performed_by = self.delivery.to_netid
        self.delivery.transfer_state = AzTransferStates.COMPLETE
        self.delivery.save()

    def set_failed_and_record_exception(self, e):
        error_message = str(e)
        AzDeliveryError.objects.create(delivery=self.delivery, message=error_message)
        self.delivery.mark_failed()
        traceback.print_exc()


class AzureProjectSummary(object):
    def __init__(self, id, based_on):
        self.id = id
        self.based_on = based_on
        self.total_size = 0
        self.file_count = 0
        self.folder_count = 0
        self.root_folder_count = 0
        self.sub_folder_count = 0
        self.error_msg = None

    def apply_path_dict(self, path_dict):
        if path_dict["is_directory"]:
            self.folder_count += 1
            # Remote paths with three parts are top level directories "netid/projectname/dirname"
            if len(path_dict["name"].split('/')) == 3:
                self.root_folder_count += 1
            else:
                self.sub_folder_count += 1
        else:
            self.total_size += path_dict["content_length"]
            self.file_count += 1


def create_project_summary(delivery):
    current_project = delivery.get_current_project()
    summary = AzureProjectSummary(id=delivery.id, based_on="project contents")
    try:
        project = AzDataLakeProject(current_project.container_url, current_project.path)
        for file_metadata in project.get_paths():
            summary.apply_path_dict(file_metadata)
    except ResourceNotFoundError:
        summary.error_msg = f"No project found at {current_project.path}."
    return summary
