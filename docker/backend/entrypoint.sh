#!/bin/sh

# Chack if database has started
if [ "$DATABASE" = "sentiment-analysis" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

until cd /app/backend
do
    echo "Waiting for server volume..."
done

set -e
python manage.py collectstatic --noinput
python manage.py migrate  --noinput
exec "$@"
