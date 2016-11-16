# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_app_push_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResponseLog',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('platform', models.CharField(max_length=4, choices=[('apns', 'Apple Push Notifications'), ('gcm', 'Google Cloud Messaging')])),
                ('roundtrip_time', models.FloatField()),
                ('available', models.BooleanField()),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
