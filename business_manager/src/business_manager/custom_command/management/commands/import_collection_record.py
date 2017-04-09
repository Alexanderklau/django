# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.core import serializers

import os, traceback, random
from datetime import datetime
import json

from business_manager.review import message_client, risk_client, redis_client
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord
from business_manager.employee.models import Employee
from business_manager.review.employee_models import get_dispatch_collector_list, get_employee
from business_manager.collection.models import *

class Command(BaseCommand):
    def handle(self, *args, **options):
        reviews = Review.objects.all().order_by('-id')[:10]
        for i in reviews:
            print i
            data = json.loads(serializers.serialize('json', [i]))[0].get('fields')
            reviewer = Employee.objects.filter(id=data['reviewer']).first()
            if reviewer:
                data['reviewer'] = reviewer.phone_no
            reviewer_done = Employee.objects.filter(id=data['reviewer_done']).first()
            if reviewer_done:
                data['reviewer_done'] = reviewer_done.phone_no

            apply = Apply.objects.filter(id=data['order']).first()
            if apply:
                repayment = apply.repayment
                if repayment:
                    data['order'] = repayment.order_number

            print data
            print data['reviewer']
            # print i._meta.fields












