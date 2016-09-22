# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-09-19 20:16
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('handover_api', '0015_auto_20160919_2007'),
    ]

    operations = [
        migrations.AlterField(
            model_name='share',
            name='from_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares_from', to='handover_api.DukeDSUser'),
        ),
        migrations.AlterField(
            model_name='share',
            name='to_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares_to', to='handover_api.DukeDSUser'),
        ),
    ]