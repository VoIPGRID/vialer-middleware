#!/bin/bash

check_up() {
    service=$1
    host=$2
    port=$3

    max=13 # 1 minute

    counter=1
    while true;do
        python -c "import socket;s = socket.socket(socket.AF_INET, socket.SOCK_STREAM);s.connect(('$host', $port))" \
        >/dev/null 2>/dev/null && break || \
        echo "Waiting that $service on ${host}:${port} is started (sleeping for 5)"

        if [ ${counter} -eq ${max} ];then
            echo "Could not connect to ${service} after some time"
            echo "Investigate locally the logs with fig logs"
            exit 1
        fi

        sleep 5

        counter=$((counter+1))
    done
}

check_up "DB Server" ${DB_PORT_3306_TCP_ADDR} ${DB_ENV_PORT}
echo "DB server up and running."

# Setup DB
python /usr/src/app/manage.py migrate --noinput
python /usr/src/app/manage.py collectstatic --noinput

# Start prometheus webserver and healthcheck the platform
python /usr/src/app/main/prometheus/prometheus.py &

# Run
exec /usr/local/bin/gunicorn --bind 0.0.0.0:8000 -w 1 -k gevent main.wsgi:application
