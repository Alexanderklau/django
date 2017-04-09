#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand, CommandError
from business_manager.collection.models import InspectionDetails

advance_inspection = [
    {"cn_name": u'对专业知识解释有误，造成客户极度抱怨不还款的（包括对公支付宝账号发送错误导致客户转错账）', "warn_level": InspectionDetails.warn_code, "trigger_level": 2},

    {"cn_name": u'私下多收客户逾期款', "warn_level": InspectionDetails.lost_code, "trigger_level": 3},
    {"cn_name": u'对客户及客户家人进行恐吓、要挟，对公司造成名誉损害', "warn_level": InspectionDetails.lost_code, "trigger_level": 3},
    {"cn_name": u'如客户需通过私人转账方式处理，催收员未向组长进行报备', "warn_level": InspectionDetails.lost_code, "trigger_level": 3},
    {"cn_name": u'未通过公司同意，私自承诺客户可以进行金额减免', "warn_level": InspectionDetails.lost_code, "trigger_level": 3},
]

class Command(BaseCommand):

    def handle(self, *args, **options):
        for item in advance_inspection:
            InspectionDetails.objects.create(**item)
