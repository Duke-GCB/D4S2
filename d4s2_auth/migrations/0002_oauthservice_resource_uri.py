# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-11-18 14:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('d4s2_auth', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='oauthservice',
            name='resource_uri',
            field=models.URLField(default='https://oauth.oit.duke.edu/oauth/resource'),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name='OAuthState',
        ),
    ]
