#!/usr/bin/env bash

#ensures database is migrated before each start of the production application
/usr/local/bin/python manage.py migrate

# Check if any data needs to be loaded
if [ -f /etc/external/fixtures.json ]; then
  /usr/local/bin/python manage.py loaddata /etc/external/fixtures.json
fi

# Apache gets grumpy about PID files pre-existing
rm -f /var/run/apache2/apache2.pid

/usr/sbin/apachectl -DFOREGROUND
