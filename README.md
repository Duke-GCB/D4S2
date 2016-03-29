DukeDS Handover Service
=======================

Web service to facilitate notification and transfer of projects in DukeDS

Usage
=====

The web service is run as a [flask](http://flask.pocoo.org) web application. To start the service for development:

    $ git clone git@github.com:Duke-GCB/DukeDSHandoverService.git
    $ cd DukeDSHandoverService
    $ virtualenv env
    $ source env/bin/activate
    $ pip install -r requirements.txt
    $ python handover_api/app.py

     * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
     * Restarting with stat
     * Debugger is active!
     * Debugger pin code: 250-138-134

The service can be consumed with HTTP and JSON, e.g. with [cURL](http://curl.haxx.se):

    curl -X POST \
      -H "Content-Type: application/json" \
      -d '{"from_user_id": "sender-dds-udid", "project_id": "existing-project-udid", "to_user_id": "recip-dds-udid"}' \
      http://127.0.0.1:5000/handovers/

The service includes the following resources:

- /handovers
- /drafts
- /users

See [schemas.py](handover_api/schemas.py) for object definitions.
