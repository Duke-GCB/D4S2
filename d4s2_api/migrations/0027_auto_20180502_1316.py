# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2018-05-02 13:16
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('d4s2_api', '0026_auto_20180430_2019'),
    ]

    operations = [
        migrations.AddField(
            model_name='ddsdeliveryerror',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2018, 5, 2, 13, 16, 20, 300083, tzinfo=utc)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='s3deliveryerror',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2018, 5, 2, 13, 16, 27, 387807, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
