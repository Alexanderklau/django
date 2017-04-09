# -*- coding: utf-8 -*-
"""
从 saas 系统导入, 员工信息
"""


from django.core.management.base import BaseCommand, CommandError
from django.db import models

import os, traceback, random
from datetime import datetime
import time
import json

from business_manager.review import message_client, risk_client, redis_client
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord
from business_manager.collection.models import *

from business_manager.config_center.models import *

from business_manager.strategy.models import Strategy2
from business_manager.import_data.services import report_data_collection_money

from django.contrib.auth.models import User
from business_manager.employee.models import Employee, Platform


class Command(BaseCommand):

    def dump_data(self):
        users = User.objects.filter()
        users_data = users.values()

        employees = Employee.objects.filter()
        employees_data = employees.values()

        datetime_fields = ['date_joined', 'last_login', 'create_at', 'update_at']
        for ud in users_data:
            for k in ud:
                if k in datetime_fields:
                    ud[k] = ud[k].strftime('%Y-%m-%d %H:%M:%S')

        for ud in employees_data:
            for k in ud:
                if k in datetime_fields:
                    ud[k] = ud[k].strftime('%Y-%m-%d %H:%M:%S')

        print users_data
        print employees_data

        data = dict(
            user=list(users_data),
            employee=list(employees_data),
        )

        return data

    def load_data(self, data):
        users_data = data['user']
        employees_data = data['employee']

        for user_data in users_data:
            print user_data
            id = user_data['id']
            user = User.objects.filter(id=id)
            if user:
                print 'user: %s exists' % user_data
                continue
            user = User(**user_data)
            user.save()
            print user

        for employee_data in employees_data:
            print employee_data
            id = employee_data['id']
            employee = Employee.objects.filter(id=id)
            if employee:
                print 'employee: %s exists' % employee_data
                continue
            employee = Employee(**employee_data)
            employee.save()
            print employee
            platform = Platform.objects.filter().first()
            employee.platform_list.add(platform)

            print employee


    def handle(self, *args, **options):
        # data = self.dump_data()
        # with open('employee_copy_from_rst.json', 'w') as f:
            # # json.dumps(data)
            # # print data
            # f.write(json.dumps(data))

        with open('employee_copy_from_rst.json') as f:
            data = json.load(f)
            self.load_data(data)


