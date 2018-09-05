
import sys

from invoke import task
from invoke.config import Config

config = Config()


@task()
def prepare(c, tag):
    with c.cd('/srv/vialer-middleware'):
        for host in config.hosts:
            print('Preparing container with tag %s on %s' % (tag, host))
            result = c.run('sudo ./deploy.sh prepare %s' % tag)
            output = result.stdout
            if 'mysql_health=1' in output and 'redis_health=1' in output:
                print('App server %s has been prepared, MySQL and Redis seem to run.' % host)
                if host != config.hosts[-1]:
                    print('Do you want to continue with the next app server? (y/n)')
                    choice = raw_input().lower()
                    if choice != 'y':
                        sys.exit()
            else:
                print ('MySQL and Redis are not reachable from the container, '
                       'investigate or rollback to the previous tag.')
                sys.exit(3)


@task()
def activate(c, tag):
    with c.cd('/srv/vialer-middleware'):
        for host in config.hosts:
            result = c.run('sudo ./deploy.sh activate %s' % tag)
            output = result.stdout
            if 'nginx -s reload' in output:
                print ('App server %s has been activated, nginx has been reloaded. '
                       'Please verify everything is running correctly.') % host
                if host != config.hosts[-1]:
                    print('Do you want to continue with the next app server? (y/n)')
                    choice = raw_input().lower()
                    if choice != 'y':
                        sys.exit()
            else:
                print('Nginx has not been reloaded, something went wrong. '
                      'Please check the container on %s' % host)
                sys.exit(8)


@task()
def staging(c):
    config.hosts = ['middleapp0-staging.voipgrid.nl', 'middleapp1-staging.voipgrid.nl', 'middleapp2-staging.voipgrid.nl']


@task()
def production(c):
    config.hosts = ['middleapp2-ams.voipgrid.nl', 'middleapp2-grq.voipgrid.nl', 'middleapp3-ams.voipgrid.nl']
