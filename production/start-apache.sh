#!/usr/bin/env bash

#ensures database is migrated before each start of the production application
/usr/local/bin/python manage.py migrate --noinput

# Check if any data needs to be loaded
if [ -f /etc/external/fixtures.json ]; then
  /usr/local/bin/python manage.py loaddata /etc/external/fixtures.json
fi

# Create/Update DukeDS configuration
python manage.py createddsendpoint "Duke Data Service" $D4S2_DDSCLIENT_URL $D4S2_DDSCLIENT_PORTAL_ROOT $D4S2_DDSCLIENT_AGENT_KEY $D4S2_DDSCLIENT_OPENID_PROVIDER_ID

# Apache gets grumpy about PID files pre-existing
rm -f /var/run/apache2/apache2.pid

/usr/sbin/apachectl -DFOREGROUND
