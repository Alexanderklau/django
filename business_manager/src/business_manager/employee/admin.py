#!/usr/bin/env python
# coding=utf-8

from django.contrib import admin
from business_manager.employee.models import *

class PlatformAdmin(admin.ModelAdmin):
    search_fields = ['name', 'show_name']

class PermissionSetAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name']
    ordering = ['-id']

class EmployeeGroupAdmin(admin.ModelAdmin):
    search_fields = ['id', 'group_name']
    ordering = ['-id']

class EmployeeAdmin(admin.ModelAdmin):
    search_fields = ['id', 'username']
    ordering = ['-id']

admin.site.register(Platform, PlatformAdmin)
admin.site.register(PermissionSet, PermissionSetAdmin)
admin.site.register(EmployeeGroup, EmployeeGroupAdmin)
admin.site.register(Employee, EmployeeAdmin)
