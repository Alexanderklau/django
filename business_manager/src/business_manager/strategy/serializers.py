# -*- coding: utf-8 -*-
import json
import arrow

from django.conf import settings

from rest_framework import serializers
from rest_framework.exceptions import APIException

from business_manager.collection.models import RepaymentInfo
from business_manager.employee.models import Employee, get_employee_platform
from business_manager.import_data.serializers import CuteSerializer
from business_manager.import_data.services import get_request_data, update_attr
from business_manager.import_data.models import USING, ACTIVE
from business_manager.strategy.models import ExtraInterest, Strategy2
from business_manager.config_center.models import Product


class ExtraInterestSerializer(CuteSerializer):
    # sys_field_show_name = serializers.CharField(source='sys_field_id.show_name')
    # sys_field_name = serializers.CharField(source='sys_field_id.name')

    def to_representation(self, obj):
        ori_data = super(ExtraInterestSerializer, self).to_representation(obj)
        data = ori_data

        # profile_field = ProfileField.objects.filter(id=ori_data['sys_field_id']).first()
        # extra_data = dict(
            # sys_field_show_name=profile_field.show_name,
            # sys_field_name=profile_field.name,
        # )
        # data.update(extra_data)
        return data

    # def to_internal_value(self, data):
        # ori_data = super(ImportFieldSerializer, self).to_internal_value(data)
        # new_data = ori_data
        # module_id = data.get('module_id')
        # if module_id:
            # module = ImportModule.objects.filter(id=module_id).first


    class Meta:
        model = ExtraInterest
        fields = ('id', 'name', 'type', 'strategy', 'value', 'value_type', 'installment_number')
        cute_retrieve_fields = ('id', 'sys_field_id')
        extra_kwargs = {'id': {'read_only': True}}


class Strategy2Serializer(CuteSerializer):

    def repay_time(self, data):
        day = data.pop('repay_time_ori_day', '')
        day = day[:10] if day else ''

        repay_time_data = {
            'type': data.pop('repay_time_type', 0),
            'day': day,
            'offset': data.pop('repay_time_offset', 0),
            'description': data.pop('repay_time_description', ''),
        }
        return repay_time_data

    def repay_time_from_request(self, data):
        print 'in repay_time_from_request'
        print data
        repay_time_type = int(data.pop('type', -1))
        if repay_time_type == -1:
            print data
            print 'out repay_time_from_request'
            return {}

        repay_time_ori_day = data.pop('day', 0)
        repay_time_day = 0
        print repay_time_ori_day
        print bool(repay_time_ori_day)
        if repay_time_type == 1:
            repay_time_ori_day = arrow.now().naive
            repay_time_day = arrow.now().day
        elif repay_time_type == 2:
            if repay_time_ori_day:
                repay_time_ori_day = arrow.get(repay_time_ori_day).naive
                repay_time_day = arrow.get(repay_time_ori_day).day
            else:
                    msg = u'还款时间错误: %s' % repay_time_ori_day
                    raise APIException(msg)

        print repay_time_day
        repay_time_data = {
            'repay_time_type': repay_time_type,
            'repay_time_ori_day': repay_time_ori_day,
            'repay_time_day': repay_time_day,
            'repay_time_offset': data.pop('offset', 0),
            'repay_time_description': data.pop('description', ''),
        }
        if repay_time_ori_day:
            repay_time_data['repay_time_ori_day'] = repay_time_ori_day

        print 'out repay_time_from_request'

        return repay_time_data


    def extra_interest(self, strategy_id):
        extra_interest = ExtraInterest.objects.filter(strategy_id=strategy_id, status__gte=0)
        # print fields
        extra_interest_data = [ExtraInterestSerializer(ei).data for ei in extra_interest if ei.type == 1]
        sub_interest_data = [ExtraInterestSerializer(ei).data for ei in extra_interest if ei.type == 2]

        data = dict(
            extra_interest=extra_interest_data,
            sub_interest=sub_interest_data,
        )

        return data

    def installment_type(self, data):
        print 'in installment_type'
        type = data.get('type', -1)
        if type == -1:
            return {}

        if type in [1, 2, 4]:
            data = dict(
                installment_days=1,
                installment_type=1,
            )
        elif type in [3]:
            data = dict(
                installment_days=data['installment_count'],
                installment_type=2,
                installment_count=1,
            )
        else:
            raise

        print 'out  installment_type'
        return data

    def extra_interest_from_request(self, data, strategy):
        print 'in extra_interest_from_request'
        extra_interest_data = data.get('extra_interest', [])
        sub_interest_data = data.get('sub_interest', [])
        for ei in extra_interest_data:
            ei['type'] = 1
            ei['strategy'] = strategy.strategy_id

        for si in sub_interest_data:
            si['type'] = 2
            si['value_type'] = 2
            si['strategy'] = strategy.strategy_id

        extra_interest_data.extend(sub_interest_data)
        data = extra_interest_data

        print 'out extra_interest_from_request'
        return data

    def using_count(self, obj):
        repayment = RepaymentInfo.objects.filter(strategy_id=obj.strategy_id)
        return repayment.count()

    def to_representation(self, obj):
        print 'in field representation'
        print obj
        ori_data = super(Strategy2Serializer, self).to_representation(obj)
        data = ori_data

        print data
        repay_time_dic = self.repay_time(data)
        repay_time_data = dict(
            repay_time=repay_time_dic,
        )
        interest_data = self.extra_interest(data['strategy_id'])

        if data['status'] in [USING]:
            data['status'] = ACTIVE
        if data['type'] in [3]:
            data['installment_count'] = data['installment_days']
        # data['using_count'] = self.using_count(obj)
        data.update(interest_data)
        data.update(repay_time_data)

        product = data['belong_product']
        data.pop('belong_product')
        data['product'] = product
        p_db = Product.objects.get(name = product, platform = obj.belong_platform)
        data['product_name'] = p_db.show_name

        return data

    def update(self, instance, validated_data):
        """creator: 从 request 中获取, 嵌套数据, 独立处理"""

        print 'in serializer create'
        print validated_data
        if not validated_data:
            msg = u'合法数据为空.'
            print msg
            print self.context['request'].data
            raise serializers.ValidationError(msg)
            pass
        request = self.context['request']

        request_data = get_request_data(self.context['request'], {})
        repay_time = request_data.get('repay_time', {})
        product = request_data.get('product', '')
        print '*' * 10
        print repay_time
        validated_data.update(self.repay_time_from_request(repay_time))
        validated_data.update(self.installment_type(validated_data))
        if product:
            validated_data['belong_product'] = product
        print validated_data
        update_attr(instance, validated_data, partial=False)
        instance.save()

        extra_interests = ExtraInterest.objects.filter(strategy=instance)
        # 每次更新 fields 对应的数据都是全量的, 所以 现将 status = -1 (删除)
        extra_interests.update(status=-1)

        # 创建 ExtraInterest
        # fields = self.context['request'].data.get('data', {}).get('fields', [])
        extra_interest_data = self.extra_interest_from_request(request_data, instance)
        print extra_interest_data
        for field in extra_interest_data:
            field_id = field.pop('id', None)
            serializer = ExtraInterestSerializer(data=field)
            print serializer.is_valid()
            print serializer.errors

            serializer.save()

        print 'out CuteSerializer create'

        return instance




    def create(self, validated_data):
        """creator: 从 request 中获取, 嵌套数据, 独立处理"""

        print 'in serializer create'
        print validated_data
        if not validated_data:
            msg = u'合法数据为空.'
            print msg
            print self.context['request'].data
            raise serializers.ValidationError(msg)
            pass
        request = self.context['request']
        self.platform = get_employee_platform(request)[0].name

        # 获取当前登录的用户
        creator = Employee.objects.filter(user=request.user).first()
        # creator = Employee.objects.filter().first()
        validated_data['creator'] = creator

        request_data = get_request_data(self.context['request'])
        repay_time = request_data.get('repay_time')
        product = request_data.get('product')
        platform = get_employee_platform(request).first().name
        validated_data['belong_platform'] = platform
        validated_data['belong_product'] = product

        print '*' * 10
        print repay_time
        validated_data.update(self.repay_time_from_request(repay_time))

        validated_data.update(self.installment_type(validated_data))
        # validated_data['strategy_id'] = Strategy2.objects.filter().order_by('-strategy_id').first().strategy_id + 1

        print validated_data
        strategy = Strategy2(**validated_data)
        strategy.save()

        # 创建 ImportField
        # fields = self.context['request'].data.get('data', {}).get('fields', [])
        extra_interest_data = self.extra_interest_from_request(request_data, strategy)
        print extra_interest_data
        for field in extra_interest_data:
            field_id = field.pop('id', None)
            serializer = ExtraInterestSerializer(data=field)
            print serializer.is_valid()
            print serializer.errors

            serializer.save()

        print 'out CuteSerializer create'

        return strategy

    def validate_name(self, value):
        print '----------------'
        #print self
        #print self.Meta
        #print value
        #print type(value)
        #print '0909' * 100
        pk = 0
        if self.instance:
            pk = self.instance.pk

        platform = get_employee_platform(self.context['request']).values_list('name', flat = True)
        model = Strategy2.objects.filter(name=value, status__gte=0, belong_platform=platform).exclude(pk=pk).first()
        if model:
            msg = u"策略 '{}', 已存在.".format(value)
            raise serializers.ValidationError(msg)

        return value


    # def validate_status(self, value):
        # print '----------------'
        # print self
        # print self.Meta
        # pk = 0
        # if self.instance:
            # pk = self.instance.pk
        # model = Strategy2.objects.filter(pk=pk, status=USING).first()
        # if model:
            # msg = u"策略 '{}', 不能修改或删除.".format(value)
            # raise serializers.ValidationError(msg)

        # return value



    class Meta:
        model = Strategy2
        fields = (
            'strategy_id', 'name', 'type', 'amount_floor', 'amount_ceil', 'interest',
            'installment_count', 'status', 'update_at', 'using_count', 'installment_days',
            'repay_time_type', 'repay_time_ori_day', 'repay_time_offset', 'repay_time_description',
            'belong_product'
        )
        # extra_kwargs = {'strategy_id': {'read_only': True}}
        read_only_fields = (
            'strategy_id', 'repay_time_type', 'repay_time_ori_day', 'repay_time_offset', 'repay_time_description',
            'installment_days',
        )




class Strategy2ListSerializer(CuteSerializer):
    def to_representation(self, obj):
        ori_data = super(Strategy2ListSerializer, self).to_representation(obj)
        data = ori_data
        if data['status'] in [USING]:
            data['status'] = ACTIVE
        product = data['belong_product']
        data.pop('belong_product')
        data['product'] = product
        try:
            p_db = Product.objects.get(name = product, platform = obj.belong_platform)
            data['product_name'] = p_db.show_name
        except Exception as e:
            print e

        return data


    class Meta:
        model = Strategy2
        fields = ('strategy_id', 'name', 'status', 'update_at', 'using_count', 'belong_product')


