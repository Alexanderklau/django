#-*- coding: utf-8 -*-
from django.contrib import admin
from business_manager.review.models import *


class ReviewAdmin(admin.ModelAdmin):
    search_fields = ['id', 'order__create_by__name', "reviewer__username"]
    readonly_fields = ['create_at']
    ordering = ['-id']

class LabelAdmin(admin.ModelAdmin):
    ordering = ['-id']

class CollectionRecordAdmin(admin.ModelAdmin):
    readonly_fields = ['create_at']
    ordering = ['-id']
    raw_id_fields = ["apply", "create_by"]

admin.site.register(Review, ReviewAdmin)
admin.site.register(Label, LabelAdmin)
admin.site.register(CollectionRecord, CollectionRecordAdmin)
