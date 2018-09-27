# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2018-09-27 15:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('d4s2_api', '0035_populate_email_template_set'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ddsdelivery',
            name='email_template_set',
            field=models.ForeignKey(help_text='Email template set to be used with this delivery', on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.EmailTemplateSet'),
        ),
        migrations.AlterField(
            model_name='s3delivery',
            name='email_template_set',
            field=models.ForeignKey(help_text='Email template set to be used with this delivery', on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.EmailTemplateSet'),
        ),
        migrations.AlterField(
            model_name='share',
            name='email_template_set',
            field=models.ForeignKey(help_text='Email template set to be used with this share', on_delete=django.db.models.deletion.CASCADE, to='d4s2_api.EmailTemplateSet'),
        ),
    ]
