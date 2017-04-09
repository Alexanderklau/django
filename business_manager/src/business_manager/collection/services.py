# -*- coding: utf-8 -*-
import json

from rest_framework import serializers
from rest_framework.exceptions import APIException

from business_manager.import_data.serializers import CuteSerializer
from business_manager.config_center.models import ProfileField, ProfileModule
from business_manager.employee.models import Employee
from business_manager.order.apply_models import Apply
from business_manager.review.models import CollectionRecord, CollectionRecordTag
from business_manager.collection.models import InstallmentDetailInfo
# from business_manager.collection.serializers import CollectionRecordSerializer



def get_apply_installment_numbers(apply):
    # apply_status = apply.status
    q = {
        'repayment': apply.repayment,
        'installment_number__gte': apply.money + 1,
        'repay_status': 2,
    }

    installments = InstallmentDetailInfo.objects.filter(**q)
    installment_numbers = [str(ins.installment_number) for ins in installments]

    print installment_numbers

    return installment_numbers


def collection_extra_data(apply):
    """催记的额外信息.

    逾期天数, 应还金额, 逾期期数, 委案金额"""
    overdue_days = apply.overdue_days
    should_repay_amount = apply.rest_repay_money
    installment_numbers = get_apply_installment_numbers(apply)
    ori_should_repay_amount = apply.ori_collection_amount

    installment_numbers_str = ",".join(installment_numbers) if installment_numbers else ""

    data = dict(
        overdue_days=overdue_days,
        should_repay_amount=should_repay_amount,
        installment_numbers=installment_numbers_str,
        ori_should_repay_amount=ori_should_repay_amount,
    )

    return data


def add_collection_record(data, request=None):

    instance = CollectionRecord(**data)
    instance.save()
    # serializer = CollectionRecordSerializer(data=data)
    # print serializer
    # serializer.is_valid(raise_exception=True)
    # # serializer.is_valid()
    # # serializer.validated_data.update(valid_data)
    # print 'data --' * 20
    # print serializer.validated_data
    # instance = serializer.save()
    # print serializer.data

    return instance


