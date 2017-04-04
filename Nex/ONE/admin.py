from django.contrib import admin
from .models import *
# 定义我自己希望显示的页面
class ArticleAdmin(admin.ModelAdmin):
    fields = ('title','desc','content','user')
admin.site.register(User)
admin.site.register(Tag)
admin.site.register(Ad)
admin.site.register(Article,ArticleAdmin)

# Register your models here.
