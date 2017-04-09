# -*- coding: utf-8 -*-
"""
数据导入模板:
    创建 profile field, profile module
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
from business_manager.import_data.models import ImportModule, ImportField
import copy

PLATFORM = 'rst'
PRODUCT = 'rst'

values = [
    (1, 'string_bank_card_id', '银行卡号', '', 'textview', '', 1, 1, 0, 1),
    (2, 'string_bank_card_name', '银行名称', '', 'textview', '', 1, 1, 0, 1),
    (3, 'string_order_number', '订单号', '', 'textview', '', 1, 1, 0, 1),
    (4, 'string_channel', '资金来源渠道', '', 'textview', '', 1, 1, 0, 1),
    (5, 'int32_installment_count', '贷款期数', '', 'textview', '', 1, 1, 0, 1),
    (6, 'int32_installment_number', '当前期数', '', 'textview', '', 1, 1, 0, 1),
    (7, 'string_should_repay_time', '应还款时间', '', 'textview', '', 1, 1, 0, 1),
    (7, 'string_pay_time', '放款时间', '', 'textview', '', 1, 1, 0, 1),
    (8, 'string_real_repay_time', '实际还款时间', '', 'textview', '', 1, 1, 0, 1),
    (9, 'int32_overdue_days', '逾期天数', '', 'textview', '', 1, 1, 0, 1),
    (10, 'int32_penalty', '罚金', '', 'textview', '', 1, 1, 0, 1),
    (11, 'int32_overdue_interest', '罚息', '', 'textview', '', 1, 1, 0, 1),
    (12, 'int32_should_repay_amount', '期款（本金、利息）', '', 'textview', '', 1, 1, 0, 1),

    # 2016-12-27 10:21:24 新增字段
    (12, 'int32_real_time_should_repay_amount', '应还金额', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_apply_start_time', '委托开始时间', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_apply_end_time', '委托结束时间', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_renew_repay_time', '续期还款时间', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_home_address', '家庭地址', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_home_city', '家庭城市', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_household_address', '户籍地址', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_wechat', '微信号', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_alipay', '支付宝号', '', 'textview', '', 1, 1, 0, 1),
    (12, 'string_repay_channel', '还款渠道', '', 'textview', '', 1, 1, 0, 1),
    (12, 'int32_installment_days', '贷款天数', '', 'textview', '', 1, 1, 0, 1),
    (12, 'int32_reduction_amount', '减免金额', '', 'textview', '', 1, 1, 0, 1),

    # 2017-01-16 15:28:08 新增字段
    (1, 'string_company_department', '客户所在部门', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_company_job_title', '客户职位', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_telephone', '座机号码', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_business_account', '对公账户', '', 'textview', '', 1, 1, 0, 1),

    (13, 'int32_real_repay_amount', '实际还款金额', '', 'textview', '', 1, 1, 0, 1),
    (14, 'string_repay_status', '还款状态', '', 'textview', '', 1, 1, 0, 1),

    # (15, 'string_contact_name1', '联系人姓名1', '', 'textview', '', 1, 1, 0, 1),
    # (16, 'string_contact_relation1', '联系人关系1', '', 'textview', '', 1, 1, 0, 1),
    # (17, 'string_contact_phone1', '联系人电话1', '', 'textview', '', 1, 1, 0, 1),

    # (18, 'string_contact_name2', '联系人姓名2', '', 'textview', '', 1, 1, 0, 1),
    # (19, 'string_contact_relation2', '联系人关系2', '', 'textview', '', 1, 1, 0, 1),
    # (20, 'string_contact_phone2', '联系人电话2', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name3', '联系人姓名3', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation3', '联系人关系3', '', 'textview', '', 1, 1, 0, 1),
    # (23, 'string_contact_phone3', '联系人电话3', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name4', '联系人姓名4', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation4', '联系人关系4', '', 'textview', '', 1, 1, 0, 1),
    # (23, 'string_contact_phone4', '联系人电话4', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name5', '联系人姓名5', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation5', '联系人关系5', '', 'textview', '', 1, 1, 0, 1),
    # (23, 'string_contact_phone5', '联系人电话5', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name6', '联系人姓名6', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation6', '联系人关系6', '', 'textview', '', 1, 1, 0, 1),
    # (26, 'string_contact_phone6', '联系人电话6', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name7', '联系人姓名7', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation7', '联系人关系7', '', 'textview', '', 1, 1, 0, 1),
    # (23, 'string_contact_phone7', '联系人电话7', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name8', '联系人姓名8', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation8', '联系人关系8', '', 'textview', '', 1, 1, 0, 1),
    # (28, 'string_contact_phone8', '联系人电话8', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name9', '联系人姓名9', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation9', '联系人关系9', '', 'textview', '', 1, 1, 0, 1),
    # (29, 'string_contact_phone9', '联系人电话9', '', 'textview', '', 1, 1, 0, 1),

    # (21, 'string_contact_name10', '联系人姓名10', '', 'textview', '', 1, 1, 0, 1),
    # (22, 'string_contact_relation10', '联系人关系10', '', 'textview', '', 1, 1, 0, 1),
    # (30, 'string_contact_phone10', '联系人电话10', '', 'textview', '', 1, 1, 0, 1),


]

values_yixin = [
    (1, 'string_case_type', '案件类型', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_city', '城市', '', 'textview', 1, 1, 0, 1),
    (1, 'string_shoubie', '手别', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_gongshi', '公司', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_user_type', '客户类型', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_should_repay_amount_all', '应还本息', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_repayed_amount_all', '已还金额', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_repayed_installment_count', '已还期数', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_repayment_create_at', '合同签订日期', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_overdue_installment_count', '逾期期数', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_lastest_repay_time', '新还时间', '', 'textview', '', 1, 1, 0, 1),
    (1, 'string_overdue_amount_all', '累计欠款', '', 'textview', '', 1, 1, 0, 1),

    (1, 'string_business_account', '对公账户', '', 'textview', '', 1, 1, 0, 1),
]

values_lanlingdai = [
    (1, 'string_renew_amount', '续期金额', '', 'textview', '', 1, 1, 0, 1),
]


def add_contact(numbers):
    values_contact = [
        [1, 'string_contact_name%s', '联系人姓名%s', '', 'textview', '', 1, 1, 0, 1],
        [2, 'string_contact_relation%s', '联系人关系%s', '', 'textview', '', 1, 1, 0, 1],
        [3, 'string_contact_phone%s', '联系人电话%s', '', 'textview', '', 1, 1, 0, 1],
    ]
    data = []
    for num in range(1, numbers + 1):
        values = copy.deepcopy(values_contact)
        for value in values:
            value[1] = value[1] % num
            value[2] = value[2] % num
        data.extend(values)

    print data
    return data



def add_prefix(datas, prefix, prefix_cn):
    result = []
    for data in datas:
        data = list(data)
        field_type, field_name = data[1].split('_', 1)
        data[1] = '%s_%s_%s' % (field_type, prefix, field_name)
        data[2] = '%s_%s' % (prefix_cn, data[2])
        result.append(data)
    return result

values_yixin = add_prefix(values_yixin, 'yixin', '宜信')
values_lanlingdai = add_prefix(values_lanlingdai, 'lanlingdai', '蓝领贷')

values.extend(add_contact(20))
values.extend(values_yixin)
values.extend(values_lanlingdai)


required_fields = [
    "string_name",
    "int32_amount",
    "string_idcard_no",
    "string_phone",
    "string_order_number",
    "string_channel",
    "int32_installment_count",
    "int32_installment_days",
    "int32_installment_number",
    "string_should_repay_time",
    "int32_overdue_days",
    "int32_real_time_should_repay_amount",
]
all_fields = [_v[1] for _v in values]

module_keys = {_k: 0 for _k in all_fields}
required_module_keys = {_k: 1 for _k in required_fields}
module_keys.update(required_module_keys)


# module_keys_yixin = {_value[1]: 0 for _value in values_yixin}
# module_keys_lanlingdai = {_value[1]: 0 for _value in values_lanlingdai}

# module_keys.update(module_keys_yixin)
# module_keys.update(module_keys_lanlingdai)

# 姓名, 身份证号码, 资金来源渠道, 联系人号码, 联系人姓名, 联系人关系
contact_field_datas = {
    u'姓名': 'string_name',
    u'身份证号码': 'string_idcard_no',
    u'资金来源渠道': 'string_channel',
    u'联系人号码': 'string_contact_name1',
    u'联系人姓名': 'string_contact_phone1',
    u'联系人关系': 'string_contact_relation1',

}

def create_import_module(field_datas):
    contact_import = dict(
        name=u'联系人导入',
        platform=PLATFORM,
        product=PRODUCT,
        # creator='',
        module_type=ImportModule.IMPORT_CONTACT,
    )
    import_modules = ImportModule.objects.filter(**contact_import)

    creator = Employee.objects.filter().first()
    contact_import['creator'] = creator
    if import_modules:
        import_modules.update(**contact_import)
        import_module = import_modules.first()
    else:
        import_module = ImportModule(**contact_import)
        import_module.save()
    print 'import_module create or update end'

    import_field = ImportField.objects.filter(module=import_module)
    import_field.update(status=-1)
    for k, v in field_datas.items():
        sys_field_id = ProfileField.objects.filter(name=v, is_delete=0).first()
        field_data = {}
        field_data['user_field_name'] = k
        field_data['platform'] = PLATFORM
        field_data['product'] = PRODUCT
        field_data['module'] = import_module
        field_data['sys_field_id'] = sys_field_id
        field_data['sys_field_name'] = sys_field_id.show_name

        import_field = ImportField(**field_data)
        import_field.save()

    print 'out create_import_module'


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            create_import_module(contact_field_datas)
            return 
            errors = []
            keys_str = 'id,name,show_name,description,type,reserve,is_inner,is_in_use,is_delete,use_times'
            keys = keys_str.split(',')
            for value in values:
                print '------'
                print value
                profile_field_data = {k:v for k,v in zip(keys, value)}
                profile_field_data['platform'] = PLATFORM
                profile_field_data.pop('id')
                print profile_field_data

                profile_field = ProfileField.objects.filter(name=profile_field_data['name'])
                if profile_field:
                    print '%s field is exist' % profile_field_data['name']
                    errors.append(profile_field_data)
                    profile_field.update(**profile_field_data)
                    continue

                profile_field = ProfileField(**profile_field_data)
                profile_field.save()

            print errors

            print 'start create profile module'

            module_fields = []
            # module_keys = {"int32_installment_count": 1, "string_idcard_front": 0, "string_email": 0, "string_should_repay_time": 1, "int32_installment_number": 1, "int32_overdue_days": 1, "string_family_address": 0, "string_contact_phone3": 0, "string_contact_name1": 0, "string_contact_name2": 0, "string_contact_name3": 0, "string_company": 0, "string_idcard_hand": 0, "string_bank_card_id": 0, "string_contact_relation3": 0, "string_contact_relation2": 0, "string_contact_relation1": 0, "string_name": 1, "string_order_number": 1, "int32_amount": 1, "string_repay_status": 0, "int32_should_repay_amount": 1, "string_company_address": 0, "string_channel": 0, "int32_overdue_interest": 0, "string_real_repay_time": 0, "string_qq": 0, "string_bank_card_name": 0, "string_phone": 1, "string_idcard_reverse": 0, "string_contact_phone1": 0, "string_contact_phone2": 0, "string_idcard_no": 0, "int32_gender": 0, "string_company_phone": 0, "int32_real_repay_amount": 1, "int32_penalty": 0, "int32_marriaged": 0}
            for k,v in module_keys.items():
                # {"field_id":602,"is_must":1}
                profile_field = ProfileField.objects.filter(name=k).first()
                if not profile_field:
                    print 'error: %s: %s' % (k, v)

                module_dict = dict(
                    field_id=profile_field.id,
                    is_must=v,
                )
                module_fields.append(module_dict)
            module_fields = json.dumps(module_fields)
            print module_fields

            module_data = dict(
                show_name='import',
                description='',
                layout='',
                required_fields=module_fields,
                optional_fields='',
                is_in_use=1,
                platform=PLATFORM,
            )
            profile_module = ProfileModule.objects.filter(show_name='import')
            if profile_module:
                profile_module.update(**module_data)
            else:
                profile_module = ProfileModule(**module_data)
                profile_module.save()
            print module_fields

            print 'create strategy'

            strategy_data = dict(
                name=u'易借金 7天',
                interest=1.1,
                installment_count=1,
                installment_days=7,
                installment_type=2,
                repay_time_type=1,
                type=3,
                belong_platform=PLATFORM,
                repay_time_description='',
            )
            q_strategy = {
                'name': u'易借金 7天',
            }
            strategy_data2 = dict(
                name=u'易借金 14天',
                interest=1.1,
                installment_count=1,
                installment_days=14,
                installment_type=2,
                repay_time_type=1,
                type=3,
                belong_platform=PLATFORM,
                repay_time_description='',
            )
            q_strategy2 = {
                'name': u'易借金 14天',
            }
 
            strategy = Strategy2.objects.filter(**q_strategy)
            if not strategy:
                strategy = Strategy2(**strategy_data)
                strategy.save()
            print strategy

            strategy2 = Strategy2.objects.filter(**q_strategy2)
            if not strategy2:
                strategy2 = Strategy2(**strategy_data2)
                strategy2.save()
            print strategy2

        except Exception, e:
            print e

