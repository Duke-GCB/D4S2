#!/bin/bash

# From https://docs.docker.com/compose/startup-order/

set -e

# Set environment variables for psql to read
export PGDATABASE=$POSTGRES_DB
export PGPASSWORD=$POSTGRES_PASSWORD
export PGUSER=$POSTGRES_USER
export PGHOST="$1"
shift
cmd="$@"

until psql -c '\l'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd
