from django.db import models

class Item(models.Model):
    name = models.CharField(max_length=250)
    description = models.TextField()

    class Meta:
        ordeing = ['name']

class Photo(models.Model):
    item = models.ForeignKey(Item)
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='photos')
    caption = models.CharField(max_length=250,blank=True)

    class Meta:
        ordeing = ['title']

    def __unicode__(self):
        return self.title

    @permalink
    def get_absolute_url(self):
        return
# Create your models here.
