# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-11-18 18:49
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('d4s2_auth', '0002_oauthservice_resource_uri'),
    ]

    operations = [
        migrations.CreateModel(
            name='OAuthToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_json', models.TextField(unique=True)),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='d4s2_auth.OAuthService')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]