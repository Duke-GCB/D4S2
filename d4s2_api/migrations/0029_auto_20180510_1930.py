# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2018-05-10 19:30
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('d4s2_api', '0028_auto_20180508_1939'),
    ]

    operations = [
        migrations.CreateModel(
            name='S3ObjectManifest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', django.contrib.postgres.fields.jsonb.JSONField(help_text='JSON array of object metadata from bucket at time of sending bucket')),
            ],
        ),
        migrations.RemoveField(
            model_name='historicals3delivery',
            name='object_manifest',
        ),
        migrations.RemoveField(
            model_name='s3delivery',
            name='object_manifest',
        ),
        migrations.AddField(
            model_name='historicals3delivery',
            name='manifest',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.S3ObjectManifest'),
        ),
        migrations.AddField(
            model_name='s3delivery',
            name='manifest',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.S3ObjectManifest'),
        ),
    ]
