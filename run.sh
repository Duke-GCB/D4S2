#!/bin/bash

# D4S2 Service startup script

set -e

# 1. Wait until postgres is ready, via https://docs.docker.com/compose/startup-order/

# Set environment variables for psql to read
export PGDATABASE=$POSTGRES_DB
export PGPASSWORD=$POSTGRES_PASSWORD
export PGUSER=$POSTGRES_USER
export PGHOST=$POSTGRES_HOST

until psql -c '\l'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# 2. Run a django migration
python manage.py migrate --noinput

# 3. Create/Update DukeDS configuration
python manage.py createddsendpoint "Duke Data Service" $D4S2_DDSCLIENT_URL $D4S2_DDSCLIENT_PORTAL_ROOT $D4S2_DDSCLIENT_AGENT_KEY $D4S2_DDSCLIENT_OPENID_PROVIDER_ID

# 4. Launch gunicorn
gunicorn -b 0.0.0.0:8000 d4s2.wsgi:application
