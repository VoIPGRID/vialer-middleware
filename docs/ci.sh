#!/bin/bash -x

set -e

# Run CI tests, start by printing a warning.
echo "Warning, this script docker containers/volumes, hit CTRL+C in 5 secs to abort."
sleep 5

touch .env

# Remove possible previous state.
docker-compose kill
docker-compose rm -vf
docker-compose build

# Wait for db service to be fully initialized.
docker-compose run --rm app ls
# Cleanup beforehand
docker-compose run --no-deps --rm app find . -name __pycache__ | xargs rm -rf;
sleep 10

# Run the tests, but disable aborting the script on errors.
set +e
docker-compose run --rm --service-ports app python manage.py test \
    --with-coverage --cover-package=. --cover-xml --cover-xml-file=coverage.xml \
    --with-xunit --xunit-file=xunit.xml
set -e

# Cleanup.
docker-compose kill
docker-compose rm -vf
