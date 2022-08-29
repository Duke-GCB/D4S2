FROM python:3.8
MAINTAINER dan.leehr@duke.edu

# Set timezone
ENV TZ=US/Eastern
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install postgres package
RUN apt-get update && apt-get install -y postgresql-client

# Install requirements
ADD requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Add application source to /app
ADD . /app/

# Set the django settings module to our docker settings file
ENV DJANGO_SETTINGS_MODULE d4s2.settings_docker

EXPOSE 8000

WORKDIR /app/

# Collect static files.
RUN D4S2_SECRET_KEY=DUMMY python manage.py collectstatic --noinput

CMD /app/run.sh
