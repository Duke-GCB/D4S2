from __future__ import unicode_literals

from django.db import models

class User(models.Model):
    dds_id = models.CharField(max_length=36)
    api_key = models.CharField(max_length=36)


class Handover(models.Model):
    STATE_CHOICES = ((0, 'Initiated'),
                     (1,'Notified',),
                     (2,'Accepted'),
                     (3,'Rejected'),)
    project_id = models.CharField(max_length=36)
    from_user_id = models.CharField(max_length=36)
    to_user_id = models.CharField(max_length=36)
    state = models.IntegerField(choices=STATE_CHOICES, default=STATE_CHOICES[0])


class Draft(models.Model):
    STATE_CHOICES = ((1,'Notified',),)
    project_id = models.CharField(max_length=36)
    from_user_id = models.CharField(max_length=36)
    to_user_id = models.CharField(max_length=36)
    state = models.IntegerField(choices=STATE_CHOICES, default=STATE_CHOICES[0])
