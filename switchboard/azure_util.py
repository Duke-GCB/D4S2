import uuid
import json
import traceback
import requests
import time
from urllib.parse import urlparse
from requests.exceptions import ReadTimeout, HTTPError
from d4s2_api.utils import MessageFactory, MessageDirection
import urllib.parse
from switchboard.userservice import get_user_for_netid
from d4s2_api.models import AzDelivery, State, AzObjectManifest, AzDeliveryError, AzTransferStates, StorageTypes
from django.conf import settings
from django.contrib.auth.models import User
from django.core.signing import Signer


AZURE_SERVICE_NAME = 'Azure Blob Storage'
DESTINATION_ALREADY_EXISTS_MSG = "Error: The transfer destination directory '{}' already exists."


class AzNotRecipientException(Exception):
    pass


class AzDestinationProjectNotSetup(Exception):
    pass


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
        if not delivery.destination_project:
            raise AzDestinationProjectNotSetup(f"No destination for delivery {delivery.id}")
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
    def transfer_delivery(delivery_id):
        transfer = AzureTransfer(delivery_id)
        try:
            transfer.ensure_transferring_state()
            transfer.notify_transfer_service()
        except Exception as e:
            transfer.set_failed_and_record_exception(e)
            print(f"Transfer {delivery_id} failed.")
            print(str(e))


class AzureTransfer(object):
    def __init__(self, delivery_id):
        self.delivery = AzDelivery.objects.get(pk=delivery_id)

    def ensure_transferring_state(self):
        if self.delivery.state != State.TRANSFERRING:
            self.delivery.mark_transferring()

    def create_delivery_data_dict(self):
        return {
            "delivery": self.delivery.pk,
            "from": self.delivery.from_netid,
            "source": self.delivery.source_project.make_project_url(),
            "to": self.delivery.to_netid,
            "destination": self.delivery.destination_project.make_project_url(),
        }

    def notify_transfer_service(self):
        # Create and store a UUID for this transfer attempt
        self.delivery.transfer_uuid = str(uuid.uuid4())
        self.delivery.save()

        # Notify the LogicApp to transfer the project
        source_storage_account, source_file_system_name = get_details_from_container_url(
            self.delivery.source_project.container_url)
        sink_storage_account, sink_file_system_name = get_details_from_container_url(
            self.delivery.destination_project.container_url)
        headers = {
            'user-agent': 'duke-data-delivery/2.0.0',
        }
        payload = {
            "Source_StorageAccount": source_storage_account,
            "Source_FileSystem": source_file_system_name,
            "Source_TopLevelFolder": self.delivery.source_project.path,
            "Sink_StorageAccount": sink_storage_account,
            "Sink_FileSystem": sink_file_system_name,
            "Sink_TopLevelFolder": self.delivery.destination_project.path,
            "Webhook_DeliveryID": self.delivery.id,
            "Webhook_TransferUUID": self.delivery.transfer_uuid,
        }
        response = requests.post(settings.TRANSFER_PIPELINE_URL, headers=headers, json=payload)
        response.raise_for_status()

    def record_object_manifest(self, file_manifest):
        manifest = self.create_delivery_data_dict()
        manifest['files'] = file_manifest
        signer = Signer()
        signed_manifest_str = signer.sign(json.dumps(manifest, default=str))
        manifest = AzObjectManifest.objects.create(content=signed_manifest_str)
        self.delivery.manifest = manifest
        self.delivery.transfer_state = AzTransferStates.CREATED_MANIFEST
        self.delivery.save()
        print("Recorded object manifest for {}.".format(self.delivery.id))

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
        self.set_failed_and_record_message(str(e))

    def set_failed_and_record_message(self, error_message):
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
    summary = AzureProjectSummary(id=delivery.id, based_on="project contents")
    summary.error_msg = "Unable to determine due to permission limitations."
    return summary


def decompose_dfs_url(url):
    parts = urlparse(url)
    account = parts.netloc.split(".")[0]
    container = parts.path.lstrip('/').split('/')[0]
    return account, container


def get_container_details(container_url):
    result = get_container_details_internal(container_url=container_url)
    # retry to better handle flaky response from Storage-as-a-Service
    if not result:
        time.sleep(0.5)
        result = get_container_details_internal(container_url=container_url)
    return result


def get_container_details_internal(container_url):
    try:
        headers = { "Saas-FileSystems-Api-Key": settings.AZURE_SAAS_KEY }
        account,container = decompose_dfs_url(container_url)
        url = f"{settings.AZURE_SAAS_URL}/api/FileSystems/{account}/{container}"
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except ReadTimeout as ex:
        return None
    except HTTPError as ex:
        return None


def get_container_owner(container_url):
    details = get_container_details(container_url)
    if details:
        return details['owner']
    else:
        return None
