# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_auto_20150826_0831'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='sandbox',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='device',
            name='sip_user_id',
            field=models.CharField(unique=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='device',
            name='token',
            field=models.CharField(max_length=250),
        ),
        migrations.AlterUniqueTogether(
            name='app',
            unique_together=set([('app_id', 'platform')]),
        ),
    ]
