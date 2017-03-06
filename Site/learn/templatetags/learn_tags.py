# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from django import template
from datetime import datetime
register = template.Library()

class Allen(template.Node):
    def __init__(self,format_string):
        self.format_string = format_string

    def render(self, context):
        return datetime.now().strftime(self.format_string)


def dateAllen(parse,token):
    try:
        tagname,format_string = token.split_contents()
    except ValueError:
        raise Te










# if __name__ == '__main__':