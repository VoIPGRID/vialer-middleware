# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-10-31 09:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_device_use_apns2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='id',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='device',
            name='sip_user_id',
            field=models.CharField(max_length=255, primary_key=True, serialize=False, unique=True),
        ),
    ]
