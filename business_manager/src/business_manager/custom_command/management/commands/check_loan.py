# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db import models

import os, traceback, random
from datetime import datetime

from TkManager.review import message_client, risk_client, redis_client
from TkManager.common.tk_log_client import TkLog
from TkManager.order.apply_models import Apply, CheckApply
from TkManager.review.models import Review, ReviewRecord, CollectionRecord
from TkManager.review.employee_models import get_dispatch_collector_list, get_employee
from TkManager.collection.models import *

class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            # 1. check_loan
            today = datetime.today().strftime("%Y-%m-%d")
            TkLog().info("check loan %s" % today)
            res = risk_client.check_loan(today)
            TkLog().info("check_loan %s" % str(res))

            collectors = get_dispatch_collector_list()
            #for collector in collectors:
            #    TkLog().info(collector.username)

            collection_applys = Apply.objects.filter(type=Apply.COLLECTION_M0, status=Apply.WAIT)
            #collection_applys = Apply.objects.filter(status=Apply.PROCESSING)

            TkLog().info("daily_loan done")

        except Exception, e:
            print e
            traceback.print_exc()
            TkLog().error("daily loan excp:%s" % str(e))

