#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q

import os, traceback, random
from datetime import datetime, date, timedelta

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.models import ContactInfo,CheckStatus, Profile, User
from business_manager.order.apply_models import Apply
# from business_manager.users.models import User, BankCard, SubChannel
from business_manager.strategy.models import Strategy2
from business_manager.collection.models import RepaymentInfo


# select repayment_id from apply where status not in ('8', '9', 'd') and type in ('a', 'b', 'c', 'd', 'e', 'g', 'h')
class Command(BaseCommand):
    def handle(self, *args, **options):
        q = {
            'type__in': ['a', 'b', 'c', 'd', 'e', 'g', 'h'],
        }
        exclude_q = {
            'status__in': ['8', '9', 'd']
        }
        apply = Apply.objects.filter(Q(**q) & ~Q(**exclude_q))
        # apply.delete()
        # repaymentids = apply.values_list('repayment')
        # repayments = RepaymentInfo.objects.filter(id__in=repayment_ids)
        # print repayments.count()
        # repayments.delete()
        # repayments.
        # print apply.count()
        # print repayment_ids.count()
        # print repayment_ids[:10]
        repayment_ids = apply.values_list('repayment__user')
        users = User.objects.filter(id__in=repayment_ids)
        # print users[:10]
        print users.count()
        users.delete()


        pass
