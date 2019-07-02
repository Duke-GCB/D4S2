#!/bin/bash

# D4S2 Service startup script

set -e

if [ -z "$POSTGRES_HOST" ]; then
  echo "ERROR: Please set POSTGRES_HOST"
  exit 1
fi

# 1. Wait for postgres to be ready
until pg_isready -h "$POSTGRES_HOST"; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 5
done

# 2. Run a django migration
python manage.py migrate --noinput

# 3. Create/Update DukeDS configuration
python manage.py createddsendpoint "Duke Data Service" $D4S2_DDSCLIENT_URL $D4S2_DDSCLIENT_PORTAL_ROOT $D4S2_DDSCLIENT_AGENT_KEY $D4S2_DDSCLIENT_OPENID_PROVIDER_SERVICE_ID $D4S2_DDSCLIENT_OPENID_PROVIDER_ID

# 4. Launch gunicorn
# gevent workers are async and needed to service streaming downloads
# with the default (sync) workers, streaming download responses time out.
gunicorn -b 0.0.0.0:8000 d4s2.wsgi:application
