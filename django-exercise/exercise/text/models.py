# coding=utf-8
from django.db import models

class Publiser(models.Model):
    company_name = models.CharField("公司名",max_length=30)
    company_address = models.CharField(max_length=60)
    company_city = models.CharField(max_length=50)
    company_web = models.URLField()
    class Meta:
        verbose_name = '公司信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.company_name


class Human(models.Model):
    name = models.CharField(max_length=30)

    class Meta:
        verbose_name = '姓名'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

class HumanDetail(models.Model):
    sex = models.BooleanField(max_length=1,choices=((0,'男'),(1,'女'),))
    email = models.EmailField()
    address = models.CharField(max_length=50)
    birthady = models.DateField()
    human = models.OneToOneField(Human)

    class Meta:
        verbose_name = '人员信息'
        verbose_name_plural = verbose_name


class Work(models.Model):
    Work_name = models.CharField(max_length=100)
    Work_human = models.ManyToManyField(Human)
    Work_company = models.ForeignKey(Publiser)
    Work_date = models.DateField()

    class Meta:
        verbose_name = '工作信息'
        verbose_name_plural = verbose_name


# Create your models here.
