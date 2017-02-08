from django.db import models
from mongoengine import *
class AritInfo(Document):
    des = StringField()
    title = StringField()
    scross = StringField()
    tags = ListField(StringField())
    meta = {
        'collection':'arti_info'
    }

# Create your models here.
