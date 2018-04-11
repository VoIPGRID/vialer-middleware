FROM python:3.4
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
		gcc \
		gettext \
		mysql-client libmysqlclient-dev \
	--no-install-recommends && rm -rf /var/lib/apt/lists/*

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

# Add requirements and install them.
ADD requirements.txt /usr/src/app
RUN pip install -r requirements.txt

# Add code.
ADD . /usr/src/app
