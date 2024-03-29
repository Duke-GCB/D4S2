# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-03-10 16:43
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('d4s2_api', '0040_emailtemplateset_group_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='AzContainerPath',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(help_text='Path in the Azure container to a directory (project)', max_length=255)),
                ('container_url', models.URLField(help_text='URL to the container where directory (project) resides')),
            ],
        ),
        migrations.CreateModel(
            name='AzDelivery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (2, 'Accepted'), (3, 'Declined'), (4, 'Failed'), (5, 'Transferring'), (6, 'Canceled')], default=0)),
                ('decline_reason', models.TextField(blank=True)),
                ('performed_by', models.TextField(blank=True)),
                ('delivery_email_text', models.TextField(blank=True)),
                ('sender_completion_email_text', models.TextField(blank=True)),
                ('recipient_completion_email_text', models.TextField(blank=True)),
                ('user_message', models.TextField(blank=True, help_text='Custom message to include about this item when sending notifications', null=True)),
                ('from_netid', models.CharField(help_text='NetID of the sending user.', max_length=255)),
                ('to_netid', models.CharField(help_text='NetID of the recipient user.', max_length=255)),
                ('share_user_ids', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=[], size=None)),
                ('transfer_state', models.IntegerField(choices=[(0, 'New'), (1, 'Created manifest'), (2, 'Transferred project'), (3, 'Added download users to project'), (4, 'Gave recipient owner permissions'), (5, 'Emailed Sender'), (6, 'Emailed Recipient'), (7, 'Delivery Complete')], default=0, help_text='State within transfer')),
                ('destination_project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='to_project', to='d4s2_api.AzContainerPath')),
                ('email_template_set', models.ForeignKey(help_text='Email template set to be used with this delivery', null=True, on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.EmailTemplateSet')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AzDeliveryError',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('delivery', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='errors', to='d4s2_api.AzDelivery')),
            ],
        ),
        migrations.CreateModel(
            name='AzObjectManifest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(help_text='Signed JSON array of object metadata from project at time of delivery')),
            ],
        ),
        migrations.CreateModel(
            name='AzStorageConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='User facing name for these storage config settings.', max_length=255)),
                ('subscription_id', models.CharField(help_text='Azure subscription id that contains the resource group.', max_length=255)),
                ('resource_group', models.CharField(help_text='Azure Resource Group containing the storage account.', max_length=255)),
                ('storage_account', models.CharField(help_text='Azure storage account containing the container (bucket).', max_length=255)),
                ('container_name', models.CharField(help_text='Azure container (bucket) where files will be stored.', max_length=255)),
                ('storage_account_key', models.CharField(blank=True, help_text='Azure storage account key.', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalAzDelivery',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'New'), (1, 'Notified'), (2, 'Accepted'), (3, 'Declined'), (4, 'Failed'), (5, 'Transferring'), (6, 'Canceled')], default=0)),
                ('decline_reason', models.TextField(blank=True)),
                ('performed_by', models.TextField(blank=True)),
                ('delivery_email_text', models.TextField(blank=True)),
                ('sender_completion_email_text', models.TextField(blank=True)),
                ('recipient_completion_email_text', models.TextField(blank=True)),
                ('user_message', models.TextField(blank=True, help_text='Custom message to include about this item when sending notifications', null=True)),
                ('from_netid', models.CharField(help_text='NetID of the sending user.', max_length=255)),
                ('to_netid', models.CharField(help_text='NetID of the recipient user.', max_length=255)),
                ('share_user_ids', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=[], size=None)),
                ('transfer_state', models.IntegerField(choices=[(0, 'New'), (1, 'Created manifest'), (2, 'Transferred project'), (3, 'Added download users to project'), (4, 'Gave recipient owner permissions'), (5, 'Emailed Sender'), (6, 'Emailed Recipient'), (7, 'Delivery Complete')], default=0, help_text='State within transfer')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('destination_project', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.AzContainerPath')),
                ('email_template_set', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.EmailTemplateSet')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('manifest', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.AzObjectManifest')),
                ('source_project', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='d4s2_api.AzContainerPath')),
            ],
            options={
                'verbose_name': 'historical az delivery',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.AddField(
            model_name='azdelivery',
            name='manifest',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.AzObjectManifest'),
        ),
        migrations.AddField(
            model_name='azdelivery',
            name='source_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='from_project', to='d4s2_api.AzContainerPath'),
        ),
    ]
