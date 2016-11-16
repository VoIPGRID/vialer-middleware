#!/bin/bash -x

set -e

COMPOSE_FILE=docker-compose.yml

# Run CI tests, start by printing a warning.
echo "Warning, this script docker containers/volumes, hit CTRL+C in 5 secs to abort."
sleep 5

touch .env

# Remove possible previous state.
sudo docker-compose -f $COMPOSE_FILE kill
sudo docker-compose -f $COMPOSE_FILE rm -vf
sudo docker-compose -f $COMPOSE_FILE build

# Wait for db service to be fully initialized.
sudo docker-compose run --rm app ls
sleep 10

# Run the tests.
set +e
RESULT=0
sudo docker-compose -f $COMPOSE_FILE run --rm --service-ports app python manage.py test \
    --with-coverage --cover-package=. --cover-xml --cover-xml-file=coverage.xml \
    --with-xunit --xunit-file=xunit.xml
EC=$?
if [ $EC -ne 0 ]; then RESULT+=1; fi

# Cleanup.
sudo docker-compose -f $COMPOSE_FILE kill
sudo docker-compose -f $COMPOSE_FILE rm -vf

exit $RESULT
