# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2019-03-06 20:00
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('d4s2_api', '0035_auto_20181226_1613'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalddsdelivery',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicalemailtemplate',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicals3delivery',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicalshare',
            name='history_change_reason',
        ),
    ]
