DukeDS Handover Service - Production
====================================

This directory contains docker and django configuration specific to production deployments.

Summary
=======

Django's included webserver is [not suitable for production deployments](https://docs.djangoproject.com/en/1.9/ref/django-admin/#runserver), so this configuration uses [Apache](http://httpd.apache.org) and [mod_wsgi](https://docs.djangoproject.com/en/1.9/howto/deployment/wsgi/modwsgi/) to serve the application.

Our apache configuration includes https transport and [Shibboleth](https://shibboleth.net) authentication, which enable secure connections and single-sign-on in our application.

The [Dockerfile](Dockerfile) here is based on `dukegcb/dukedshandoverservice`, but installs the necessary local configurations (shibboleth, apache) and services to host the handoverservice.

It also runs `manage.py collectstatic`, which places static files (JavaScript, CSS, Images) into a directory served by Apache. This is baked into the image, and ready for deployment.
