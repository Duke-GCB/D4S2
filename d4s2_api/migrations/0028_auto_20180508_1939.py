# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2018-05-08 19:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('d4s2_api', '0027_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicals3delivery',
            name='object_manifest',
            field=models.TextField(default='', help_text='JSON array of object metadata from bucket at time of sending bucket'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='s3delivery',
            name='object_manifest',
            field=models.TextField(default='', help_text='JSON array of object metadata from bucket at time of sending bucket'),
            preserve_default=False,
        ),
    ]