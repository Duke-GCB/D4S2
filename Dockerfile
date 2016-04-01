FROM django:python2-onbuild
MAINTAINER dan.leehr@duke.edu

COPY handoverservice/settings.docker /usr/src/app/handoverservice/settings.py
