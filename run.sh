#!/bin/bash

# D4S2 Service startup script

set -e

# 4. Launch gunicorn
gunicorn -b 0.0.0.0:8000 d4s2.wsgi:application
