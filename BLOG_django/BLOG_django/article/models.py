from django.db import models
class Article(models.Model):
    title = models.CharField(max_length=30)
    content = models.TextField()
# Create your models here.
