# Deploy commands
This folder contains commands used for development and for production. It also
contains the UWSGI settings used to run the project. These commands are ran
by docker-compose. Although these scripts could work without docker(-compose)
that would require you to setup the environment yourself
(pip packages, database etc.).

## run.sh
This script is used for a production environment. This script does the following
things:

 * Check if the database is up and running;
 * Applying database migrations that have to be done;
 * Running collectstatic for the admin interface;
 * Execute UWSGI with the settings file provided in this folder.

## run_debug.sh
This script is used for development and should never be used in a production
environment. The script does:

 * Check if the database is up and running;
 * Applying database migrations that have to be done;
 * Starting the django development server with runserver.

## docker-compose.yml
The default docker-compose.yml in this repo uses the run_debug.sh script. If
you want to run this with docker-compose in production we would suggest to
create a production.yml (also in .gitignore) and start the containers using
that file. This can be done by `docker-compose -f production.yml COMMANDS`.

## optional
These scripts are not required to run the project but just there to make
life a little bit easier. You can easily replace the command that is executed
(for development) by docker-compose with a simple
`python manage.py runserver 0:8000` for instance.
