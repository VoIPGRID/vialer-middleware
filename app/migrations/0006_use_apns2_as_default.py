# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-12 11:04
from __future__ import unicode_literals

from django.db import migrations


def forwards(apps, schema_editor):
    """
    Enable the use_apns2 flag for every device.
    """
    Device = apps.get_model('app', 'Device')

    # Query devices (~10.000) that have use_apns2=False and flip their bools.
    Device.objects.filter(use_apns2=False).update(use_apns2=True)


def backwards(apps, schema_editor):
    """
    Disable the use_apns2 flag for every device.
    """
    Device = apps.get_model('app', 'Device')

    # Query devices (~10.000) that have use_apns2=True and flip their bools.
    Device.objects.filter(use_apns2=True).update(use_apns2=False)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_use_sip_user_id_as_pk_for_device'),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
