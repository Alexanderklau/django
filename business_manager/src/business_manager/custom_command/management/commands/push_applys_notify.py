# -*- coding:utf-8 -*-
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.cache import cache

from business_manager.order.apply_models import Apply
from business_manager.util.wechat_notify_util import gen_key


class Command(BaseCommand):

    def handle(self, *args, **options):
        applys = Apply.objects.filter(promised_repay_time__gt=datetime.now(), employee__isnull=False)
        for app in applys:
            print("app: %s" %app)
            self.save_to_cache(app)

    def save_to_cache(self, app):
        key = gen_key(app.promised_repay_time, app.id)
        keep_time = (app.promised_repay_time - datetime.now()).seconds
        cache.set(key, app.repayment.order_number, keep_time + 10)
        print("save key: %s, %s, %s" % (key, app.id, keep_time))

