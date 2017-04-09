#-*- coding: utf-8 -*-

from django.contrib import admin
from business_manager.strategy.models import *


class Strategy2Admin(admin.ModelAdmin):
    # search_fields = ['id', 'order__create_by__name', "reviewer__username"]
    # readonly_fields = ['create_at']
    ordering = ['-strategy_id']

class ExtraInterestAdmin(admin.ModelAdmin):
    ordering = ['-id']


admin.site.register(Strategy2, Strategy2Admin)
admin.site.register(ExtraInterest, ExtraInterestAdmin)
