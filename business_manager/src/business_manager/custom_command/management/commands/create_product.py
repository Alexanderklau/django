#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand
from business_manager.config_center.models import Product

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if len(args) < 1:
            print 'need param platform'
            return
        p = Product(name = 'product1', show_name = u'测试产品1', description ='', service_id = '385168da-6059-11e6-9571-00163e004d3e',
                   platform = args[0], is_in_use = 1)
        p.save()
        p = Product(name = 'product2', show_name = u'测试产品2', description ='', service_id = '385168da-6059-11e6-9571-00163e004d3e',
                   platform = args[0], is_in_use = 1)
        p.save()
        p = Product(name = 'product3', show_name = u'测试产品3', description ='', service_id = '385168da-6059-11e6-9571-00163e004d3e',
                   platform = args[0], is_in_use = 1)
        p.save()

