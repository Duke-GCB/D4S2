DukeDS Handover Service
=======================

Web service to facilitate notification and transfer of projects in DukeDS

Installation
============

1. Clone the repository
2. Install dependencies

        pip install requirements.txt

3. Create a settings.py file:

        cp handoverservice/settings.template handoverservice/settings.py

4. Edit the `settings.py` file to populate the `DDSCLIENT_PROPERTIES` with a the DukeDS API URL and a software agent key, e.g.

        DDSCLIENT_PROPERTIES = {
          'url': 'https://uatest.dataservice.duke.edu/api/v1',
          'agent_key': '37a9cc3b5ed69bc96081e98478c009bb',
        }

5. Create the database schema:

        $ python manage.py migrate

6. Start the app:

        $ python manage.py runserver

7. The server is running and the API can be explored at [http://127.0.0.1:8000/api/v1/](http://127.0.0.1:8000/api/v1/)

Usage
=====

The Handover Service communicates with the Duke Data Service API as a software agent. For this to work, users must register their UDID and User Key with the Handover service, so that it may act on their behalf.

## Registering a user

        $ curl -X POST \
          -H "Content-Type: application/json" \
          -d '{"dds_id":"your-uuid","api_key":"your-user-key"}' \
          http://127.0.0.1:8000/api/v1/users
          {"id":1,"url":"http://127.0.0.1:8000/api/v1/users/1/","dds_id":"xxxx","api_key":"xxxx"}

## Sending a Draft

The term draft is used to refer to a project that is about to be handed over from a sender to a receiver. The sender is expected to use the [DukeDSClient](https://github.com/Duke-GCB/DukeDSClient) to create and upload a project. Prior to review/acceptance by the receiver, it is in a "draft" state. The Handover service can send an email to the receiver, notifying them the data in the project is ready for their review.


1. Create a Draft:

        $ curl -X POST \
          -H "Content-Type: application/json" \
          -d '{"project_id": "project-dds-uuid", "from_user_id": "from-user-uuid", "to_user_id": "5dd78297-1604-457c-87c1-e3a792be16b9"}' \
          http://127.0.0.1:8000/api/v1/drafts/
          {"id":1,"url":"http://127.0.0.1:8000/api/v1/drafts/1/","project_id":"xxxx","from_user_id":"xxxx","to_user_id":"xxxx","state":0}

2. Send the email (**Without changing settings.py to activate a real email backend, emails will only be printed to the django console**)

        $ curl -X POST http://127.0.0.1:8000/api/v1/drafts/1/send/
            {"id":1,"url":"http://127.0.0.1:8000/api/v1/drafts/1/","project_id":"xxxx","from_user_id":"xxxx","to_user_id":"xxxx","state":1}

Notice the state change, and the running django server should print out the email to the console
