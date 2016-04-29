FROM dukegcb/dukedshandoverservice
MAINTAINER dan.leehr@duke.edu

# apache2 / supervisor
RUN apt-get update \
  && apt-get install -y apache2 libapache2-mod-shib2 libapache2-mod-wsgi\
  && apt-get clean
RUN pip install supervisor supervisor-stdout

# Configure supervisor
ADD supervisord.conf /etc/supervisord.conf

# Configure Apache
ADD handoverservice.conf /etc/apache2/sites-available/handoverservice.conf
RUN a2enmod ssl
RUN a2ensite handoverservice
# Configure Shibboleth
RUN mkdir -p /var/run/shibboleth

# Place shibboleth config, duke cert, and customized attribute map
ADD shibboleth2.xml /etc/shibboleth/shibboleth2.xml
ADD attribute-map.xml /etc/shibboleth/attribute-map.xml
ADD https://shib.oit.duke.edu/idp_signing.crt /etc/shibboleth/idp_signing.crt

# Ensure services are stopped so that supervisor can run them
RUN service apache2 stop
RUN service shibd stop

# Additional requirements for production instance
COPY requirements-production.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements-production.txt

# Replace settings with production-specific
COPY settings.docker-production /usr/src/app/handoverservice/settings.py

# Place static files using manage.py
# Running any manage.py commands require a secret key to be present
# in the django app's settings.py.
ENV HANDOVERSERVICE_SECRET_KEY=secret
RUN python manage.py collectstatic --noinput
# Reset the variable to an empty string, requiring it to be provided at runtime
ENV HANDOVERSERVICE_SECRET_KEY=''

# Volume for certificates

VOLUME /etc/external/

EXPOSE 80
EXPOSE 443

CMD supervisord -c /etc/supervisord.conf -n

