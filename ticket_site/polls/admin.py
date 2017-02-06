from django.contrib import admin
from .models import *

admin.site.register(Choice)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['pub_date']
    earch_fields = ['question_text']
    # list_display = ('question_text', 'pub_date', 'was_published_recently')

# Register your models here.
admin.site.register(Question,QuestionAdmin)