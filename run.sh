#!/bin/bash

# D4S2 Service startup script

set -e

# 1. Run a django migration
python manage.py migrate --noinput

# 2. Create/Update DukeDS configuration
python manage.py createddsendpoint "Duke Data Service" $D4S2_DDSCLIENT_URL $D4S2_DDSCLIENT_PORTAL_ROOT $D4S2_DDSCLIENT_AGENT_KEY $D4S2_DDSCLIENT_OPENID_PROVIDER_ID

# 3. Launch gunicorn
gunicorn -b 0.0.0.0:8000 d4s2.wsgi:application
