# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-04-10 07:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_auto_20171123_1039'),
    ]

    operations = [
        migrations.AddField(
            model_name='app',
            name='partner_logentries_token',
            field=models.CharField(blank=True, default='', max_length=255, null=True),
        ),
    ]
