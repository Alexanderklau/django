#!/usr/bin/env python
# coding=utf-8

from django.contrib import admin
from business_manager.merchant.models import *

class StoreAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name', 'phone']
    ordering = ['-id']

class CommodityAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name']
    ordering = ['-id']

class MerchantAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name']
    ordering = ['-id']

class SalesmanAdmin(admin.ModelAdmin):
    search_fields = ['id', 'employee__username']
    ordering = ['-id']

class RegionalManagerAdmin(admin.ModelAdmin):
    search_fields = ['id', 'employee__username']
    ordering = ['-id']

admin.site.register(Store, StoreAdmin)
admin.site.register(Commodity, CommodityAdmin)
admin.site.register(Merchant, MerchantAdmin)
admin.site.register(Salesman, SalesmanAdmin)
admin.site.register(RegionalManager, RegionalManagerAdmin)
