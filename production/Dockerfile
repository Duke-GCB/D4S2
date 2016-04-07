FROM dukegcb/dukedshandoverservice
MAINTAINER dan.leehr@duke.edu

# nginx / supervisor
RUN apt-get update && apt-get install -y nginx
RUN pip install supervisor supervisor-stdout

ADD supervisord.conf /etc/supervisord.conf
ADD nginx.conf /etc/nginx/nginx.conf

RUN service nginx stop

# Place static files using manage.py
# Running any manage.py commands require a secret key to be present
# in the django app's settings.py.
ENV HANDOVERSERVICE_SECRET_KEY=secret
RUN python manage.py collectstatic --noinput
# Reset the variable to an empty string, requiring it to be provided at runtime
ENV HANDOVERSERVICE_SECRET_KEY=''

EXPOSE 80
CMD supervisord -c /etc/supervisord.conf -n

