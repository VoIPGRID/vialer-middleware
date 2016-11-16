# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.core.management import call_command
from django.db import models, migrations


def set_default_app(*args):
    call_command('loaddata', 'app/fixtures/initial_data.json')
    pass


def reverse_default_app(*args):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='App',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('platform', models.CharField(choices=[('apns', 'Apple Push Notifications'), ('gcm', 'Google Cloud Messaging')], max_length=4)),  # noqa
                ('app_id', models.CharField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name='device',
            name='app',
            field=models.ForeignKey(null=True, to='app.App'),
        ),
        migrations.RunPython(
            set_default_app,
            reverse_default_app,
        ),
        migrations.AlterUniqueTogether(
            name='device',
            unique_together=set([('token', 'app'), ('sip_user_id', 'app')]),
        ),
        migrations.RunSQL(
            "UPDATE app_device SET app_id = (SELECT MIN(id) FROM app_app WHERE app_app.platform = app_device.platform);",  # noqa
            "UPDATE app_device SET app_id = NULL",
        ),
        migrations.AlterField(
            model_name='device',
            name='app',
            field=models.ForeignKey(null=False, to='app.App'),
        ),
        migrations.RemoveField(
            model_name='device',
            name='platform',
        ),

    ]
