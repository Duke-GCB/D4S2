# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-04-25 22:40
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('handover_api', '0007_handover_reject_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalDraft',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('project_id', models.CharField(max_length=36)),
                ('from_user_id', models.CharField(max_length=36)),
                ('to_user_id', models.CharField(max_length=36)),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (4, 'Failed')], default=0)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical draft',
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalHandover',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('project_id', models.CharField(max_length=36)),
                ('from_user_id', models.CharField(max_length=36)),
                ('to_user_id', models.CharField(max_length=36)),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (2, 'Accepted'), (3, 'Rejected')], default=0)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('reject_reason', models.TextField(blank=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical handover',
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
    ]
