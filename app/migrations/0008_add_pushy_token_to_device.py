# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_remove_device_use_apns2'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='pushy_token',
            field=models.CharField(max_length=250, null=True),
        ),
    ]

