# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from  django import forms

class PublisherForm(forms.Form):
    company_name = forms.CharField(label="名称",error_messages={'required':'这个项目必须填写'})
    company_address = forms.CharField(label="地址")
    company_city = forms.CharField(label="城市")
    company_web = forms.URLField(label="网页")










# if __name == '__main__':