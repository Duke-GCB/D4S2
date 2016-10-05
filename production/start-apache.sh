#!/usr/bin/env bash

#ensures database is migrated before each start of the production application
/usr/local/bin/python manage.py migrate

/usr/sbin/apachectl -DFOREGROUND
