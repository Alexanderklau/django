#-*- coding:utf-8 -*-
from django.db import models

class Event(models.Model):
    name = models.CharField(max_length=100,help_text='姓名')
    limit = models.IntegerField(help_text='参加人数')
    status = models.BooleanField()

# Create your models here.
