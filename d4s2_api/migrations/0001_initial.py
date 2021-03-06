# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-09-23 15:48
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

TEMPLATE_TYPES = (
    'share_file_downloader',
    'share_project_viewer',
    'share_file_editor',
    'share_file_uploader',
    'share_project_admin',
    'delivery',
    'accepted',
    'declined',
)


def load_email_template_types(apps, schema_editor):
    EmailTemplateType = apps.get_model("d4s2_api", "EmailTemplateType")
    for template_type in TEMPLATE_TYPES:
        EmailTemplateType.objects.create(name=template_type)


def unload_email_template_types(apps, schema_editor):
    EmailTemplateType = apps.get_model("d4s2_api", "EmailTemplateType")
    EmailTemplateType.objects.delete(name__in=TEMPLATE_TYPES)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0007_alter_validators_add_error_messages'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Delivery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (2, 'Accepted'), (3, 'Declined')], default=0)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('decline_reason', models.TextField(blank=True)),
                ('performed_by', models.TextField(blank=True)),
                ('delivery_email_text', models.TextField(blank=True)),
                ('completion_email_text', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='DukeDSProject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_id', models.CharField(max_length=36, unique=True)),
                ('name', models.TextField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='DukeDSUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dds_id', models.CharField(max_length=36, unique=True)),
                ('api_key', models.CharField(max_length=36, null=True, unique=True)),
                ('full_name', models.TextField(null=True)),
                ('email', models.EmailField(max_length=254, null=True)),
                ('user', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('subject', models.TextField()),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='EmailTemplateType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalDelivery',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (2, 'Accepted'), (3, 'Declined')], default=0)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('decline_reason', models.TextField(blank=True)),
                ('performed_by', models.TextField(blank=True)),
                ('delivery_email_text', models.TextField(blank=True)),
                ('completion_email_text', models.TextField(blank=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('from_user', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.DukeDSUser')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.DukeDSProject')),
                ('to_user', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.DukeDSUser')),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical delivery',
            },
        ),
        migrations.CreateModel(
            name='HistoricalEmailTemplate',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('body', models.TextField()),
                ('subject', models.TextField()),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('group', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='auth.Group')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('owner', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('template_type', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.EmailTemplateType')),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical email template',
            },
        ),
        migrations.CreateModel(
            name='HistoricalShare',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (4, 'Failed')], default=0)),
                ('email_text', models.TextField(blank=True)),
                ('role', models.TextField(default='file_downloader')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('from_user', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.DukeDSUser')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.DukeDSProject')),
                ('to_user', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.DukeDSUser')),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical share',
            },
        ),
        migrations.CreateModel(
            name='Share',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (4, 'Failed')], default=0)),
                ('email_text', models.TextField(blank=True)),
                ('role', models.TextField(default='file_downloader')),
                ('from_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares_from', to='d4s2_api.DukeDSUser')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.DukeDSProject')),
                ('to_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares_to', to='d4s2_api.DukeDSUser')),
            ],
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='template_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.EmailTemplateType'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='from_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries_from', to='d4s2_api.DukeDSUser'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.DukeDSProject'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='to_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries_to', to='d4s2_api.DukeDSUser'),
        ),
        migrations.AlterUniqueTogether(
            name='share',
            unique_together=set([('project', 'from_user', 'to_user', 'role')]),
        ),
        migrations.AlterUniqueTogether(
            name='emailtemplate',
            unique_together=set([('group', 'template_type')]),
        ),
        migrations.AlterUniqueTogether(
            name='delivery',
            unique_together=set([('project', 'from_user', 'to_user')]),
        ),
        migrations.RunPython(load_email_template_types, reverse_code=unload_email_template_types),
    ]
