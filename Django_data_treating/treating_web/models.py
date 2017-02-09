from django.db import models
from mongoengine import *
from mongoengine import connect
connect('Game',host='127.0.0.1',port=27017)
class Game_info(Document):

    title = StringField()
    star = StringField()
    date = StringField()
    ID = StringField()
    type = StringField()

    # des = StringField()
    # title = StringField()
    # scross = StringField()
    # tags = ListField(StringField())
    meta = {
        'collection':'GameMessage'
    }
for i in Game_info.objects[:1]:
    print(i.title,i.star,i.date,i.ID,i.type)

# Create your models here.
