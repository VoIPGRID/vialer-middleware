# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('name', models.CharField(blank=True, null=True, max_length=255)),
                ('sip_user_id', models.CharField(blank=True, unique=True, null=True, max_length=255)),
                ('os_version', models.CharField(blank=True, null=True, max_length=255)),
                ('client_version', models.CharField(blank=True, null=True, max_length=255)),
                ('platform', models.CharField(choices=[('apns', 'Apple Push Notifications'), ('gcm', 'Google Cloud Messaging')], blank=True, null=True, max_length=4)),
                ('token', models.CharField(blank=True, null=True, max_length=250)),
                ('last_seen', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='device',
            unique_together=set([('token', 'platform')]),
        ),
    ]
