from django.contrib import admin
from .models import *


class Articleadmin(admin.ModelAdmin):
    fields = ('title','desc','content')#显示title,desc,content三项
    #exclude = ('title','desc','content') 除三项外都显示
    class Media:
        js = (
            '/static/js/kindeditor/kindeditor-min.js',
            '/static/js/kindeditor/lang/zh_CN.js',
            '/static/js/kindeditor/config.js',
        )

admin.site.register(User)
admin.site.register(Tag)
admin.site.register(Category)
# admin.site.register(ArticleManager)
admin.site.register(Article,Articleadmin)
admin.site.register(Comment)
admin.site.register(Links)
admin.site.register(Ad)

# Register your models here.
