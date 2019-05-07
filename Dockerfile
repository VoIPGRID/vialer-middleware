FROM python:3.6-stretch
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
		gcc \
		gettext \
        mysql-client \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

# Add requirements and install them.
ADD requirements.txt /usr/src/app
RUN pip install -r requirements.txt

# Add code.
ADD . /usr/src/app

CMD /usr/src/app/deploy/run.sh
