#!/usr/bin/env python
# Monkey patch to make sure libs are gevent compat.
from gevent import monkey; monkey.patch_all()  # noqa

import os
import sys


if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
