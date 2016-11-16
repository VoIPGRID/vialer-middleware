# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_auto_20150930_1403'),
    ]

    operations = [
        migrations.AddField(
            model_name='app',
            name='push_key',
            field=models.CharField(default='temp', max_length=255),
            preserve_default=False,
        ),
    ]
