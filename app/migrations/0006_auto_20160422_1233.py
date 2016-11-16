# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_responselog'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='device',
            unique_together=set([]),
        ),
    ]
