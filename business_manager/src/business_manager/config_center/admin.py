#!/usr/bin/env python
# coding=utf-8

from django.contrib import admin
from business_manager.config_center.models import *

class ProfileFieldAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name', 'type', 'description']

class ProfileModuleAdmin(admin.ModelAdmin):
    search_fields = ['id', 'description']

class ProfileFlowAdmin(admin.ModelAdmin):
    search_fields = ['id', 'description']

class WorkFlowAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name']


class WorkStatusAdmin(admin.ModelAdmin):
    search_fields = ['id', 'name', 'other_name', 'status_code', 'workflow']

class StatusFlowAdmin(admin.ModelAdmin):
    search_fields = ['id', 'flow_id']

class ExperimentPercentageAdmin(admin.ModelAdmin):
    search_fields = ['id', 'experiment_name']

class ReviewExperimentAdmin(admin.ModelAdmin):
    search_fields = ['id', 'filter', 'model_id']

class ProductAdmin(admin.ModelAdmin):
    search_fields = ['id', 'show_name']

admin.site.register(ProfileField, ProfileFieldAdmin)
admin.site.register(ProfileModule, ProfileModuleAdmin)
admin.site.register(ProfileFlow, ProfileFlowAdmin)
admin.site.register(ExperimentPercentage, ExperimentPercentageAdmin)
admin.site.register(ReviewExperiment, ReviewExperimentAdmin)
admin.site.register(WorkFlow, WorkFlowAdmin)
admin.site.register(WorkStatus, WorkStatusAdmin)
admin.site.register(StatusFlow, StatusFlowAdmin)
admin.site.register(Product, ProductAdmin)
