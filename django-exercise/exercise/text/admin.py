from django.contrib import admin
from .models import *
@admin.register(Publiser)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('company_name','company_city')
    search_fields = ('company_name','company_city')
    fields = ('company_name','company_web')
# admin.site.register(Publiser,PublisherAdmin)
admin.site.register(Human)
admin.site.register(HumanDetail)
admin.site.register(Work)
# Register your models here.
