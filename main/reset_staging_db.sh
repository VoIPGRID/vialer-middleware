#!/usr/bin/env bash

if [[ $VG_API_BASE_URL == *'staging'* ]]; then
    echo "Do you want to reset the staging database? Pick a number:"
    select yn in "Yes" "No"; do
        case $yn in
            Yes )
                echo "yes" | docker-compose run -e PYTHONUNBUFFERED=1 app ./manage.py reset_db
                docker-compose run -e SKIP_MIGRATE=1 app ./manage.py migrate --noinput --run-syncdb
                docker-compose run app ./manage.py migrate --fake
                docker-compose run app ./manage.py generate_db
                break;;
            No )
                exit;;
        esac
    done
else
    echo 'No staging VoIPGRID URL so we are not resetting the DB!'
fi