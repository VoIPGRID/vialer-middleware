FROM django:onbuild

RUN pip install -U pip

RUN apt-get update && apt-get install -y \
   nano \
   vim

WORKDIR /usr/src/app/
