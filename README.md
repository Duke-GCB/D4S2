D4S2: DukeDS Data Delivery Service
==================================

Web service to facilitate notification and transfer of projects in DukeDS

Installation - Local
====================

1. Clone the repository
2. Install dependencies

        pip install -r requirements.txt

3. Create a `settings.py` file:

        cp d4s2/settings.template d4s2/settings.py

4. Create the database schema:

        $ python manage.py migrate

5. Create a superuser (A user account is required for making authenticated API requests)

        $ python manage.py createsuperuser

6 . Register an application with a Duke DS instance and create a DDSEndpoint with the URLs, agent key, and provider id

        $ python manage.py createddsendpoint \
          endpoint-name \
          https://api.dataservice.duke.edu/api/v1 \
          registered-application-agent-key \
          https://dataservice.duke.edu \
          openid-provider-id

7. Start the app:

        $ python manage.py runserver

8. Start the background task runner:

        $ python manage.py process_tasks

9. The server is running and the API can be explored at [http://127.0.0.1:8000/api/v1/](http://127.0.0.1:8000/api/v1/)


Installation - Docker Compose
=============================

1. Clone the repository
2. Create a `d4s2.env` file

        cp d4s2.env.sample d4s2.env

3. Edit the `d4s2.env` file to populate the your DukeDS API details, a django key, and a database username/password to use:

        D4S2_SECRET_KEY=some-random-string
        D4S2_DDSCLIENT_URL=https://dataservice-host/api/v1
        POSTGRES_USER=d4s2_user
        POSTGRES_PASSWORD=some-random-password
        POSTGRES_DB=d4s2_db

4. Create the database schema:

        $ docker-compose run web python manage.py migrate

5. Create a superuser (A user account is required for making authenticated API requests)

        $ docker-compose run web python manage.py createsuperuser

6. Start the app:

        $ docker-compose up

7. The server is running and the API can be explored at  [http://your-docker-host:8000/api/v1/](http://your-docker-host:8000/api/v1/)

Usage
=====

## Creating Email templates and users

D4S2 sends emails to notify recipients of data deliveries and other actions. To share or deliver data using D4S2, sending users must belong to **groups**. Each group must have a set of email templates registered for the actions its users will perform (share, delivery, accept, decline, etc).

The email templates are intended to be specific to a group of users (such as a data-generating core facility), so there is no default group.

Groups and users can be registered with a manage.py command. To register user with NetID **ba123** and add to group **informatics**, use the following:

      python manage.py registeruser ba123@duke.edu informatics

Groups, users, and Email templates can also be administered via the Django Admin application:

1. Login to admin at http://127.0.0.1:8000/admin (using your superuser account)
2. Create email templates manually for each action and group or load the samples:

        python manage.py loaddata emailtemplates.json

Sample templates included are linked to the group with id 1 and the user with id 1.

## Sharing a project

Sharing a project is done by granting permissions to additional users, then notifying those users via email.

This application is responsible for sending emails to the recipients, based on the roles they are given.

1. Create a Django group, add django user to group. Must correspond to
2. Create an email template, associate with group and role
3. Create a Share:

        $ curl -X POST \
          -H "Authorization: X-DukeDS-Authorization <JWT from DukeDS>"
          -H "Content-Type: application/json" \
          -d '{"project_id": "project-dds-uuid", "from_user_id": "from-user-uuid", "to_user_id": "to-user-uuid", "role": "file_downloader" } \
          http://127.0.0.1:8000/api/v1/shares/
          {"id":1,"url":"http://127.0.0.1:8000/api/v1/shares/1/","project_id":"xxxx","from_user_id":"xxxx","to_user_id":"xxxx","state":0}

2. Send the email (**Without changing settings.py to activate a real email backend, emails will only be printed to the django console**)

        $ curl -X POST http://127.0.0.1:8000/api/v1/shares/1/send/
            {"id":1,"url":"http://127.0.0.1:8000/api/v1/shares/1/","project_id":"xxxx","from_user_id":"xxxx","to_user_id":"xxxx","state":1}

Notice the state change, and the running django server should print out the email to the console
