#!/bin/bash

set -e

pg_host="$1"
pg_user="$2"
shift
cmd="$@"

until psql -h "$pg_host" -U "$pg_user" -c '\l'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd
