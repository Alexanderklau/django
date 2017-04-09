#!/usr/bin/env python
# coding=utf-8

# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User

from django.dispatch import receiver
from django.db.models import Q
from django.db.models.signals import post_migrate#, post_syncdb

from business_manager.employee.models import Employee

class Store(models.Model):
    name = models.CharField(max_length = 255, help_text=u'门店店名')
    province = models.CharField(max_length = 32, help_text = u'省份')
    city = models.CharField(max_length = 32, help_text = u'城市')
    district = models.CharField(max_length = 32, help_text = u'区县')
    address = models.CharField(max_length = 255, help_text = u'具体地址')
    phone = models.CharField(max_length = 32, help_text = u'门店电话')
    is_active = models.IntegerField(default = 1, help_text = u'是否正常营业')
    belong_merchant = models.ForeignKey('Merchant')
    belong_salesman = models.ForeignKey('Salesman')

    class Meta:
        db_table = 'store'

class Commodity(models.Model):
    #商品表，暂时没有用到
    name = models.CharField(max_length = 255, help_text = u'商品名')
    price = models.IntegerField(help_text = u'商品价格')
    belong_store = models.ForeignKey(Store)

    class Meta:
        db_table = 'commodity'

class Merchant(models.Model):
    name = models.CharField(max_length = 255, help_text = u'商户名')
    phone = models.CharField(max_length = 32, help_text = u'商户电话')
    desc = models.CharField(max_length = 255, help_text = u'商户简介')

    class Meta:
        db_table = 'merchant'

class Salesman(models.Model):
    employee = models.ForeignKey(Employee)
    belong_manager = models.ForeignKey('RegionalManager')

    class Meta:
        db_table = 'salesman'

class RegionalManager(models.Model):
    employee = models.ForeignKey(Employee)

    class Meta:
        db_table = 'regionalmanager'

def get_salesman(request):
    try:
        staff = Employee.objects.get(user = request.user)
        salesman = Salesman.objects.get(employee = staff)
        return salesman
    except Exception:
        return None

def get_regional_manager(request):
    try:
        staff = Employee.objects.get(user = request.user)
        manager = RegionalManager.objects.get(employee = staff)
        return manager
    except Exception:
        return None
