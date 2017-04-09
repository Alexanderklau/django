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
from business_manager.collection.models import QualityControlRecord
from business_manager.collection.services import collection_extra_data


class CollectionRecordTagSerializer(CuteSerializer):

    # def create(self, validated_data):
        # """creator: 从 request 中获取, fields 嵌套数据, 独立处理"""

        # print 'in create'
        # print validated_data
        # if not validated_data:
            # msg = u'合法数据为空.'
            # print msg
            # print self.context['request'].data
            # raise serializers.ValidationError(msg)

        # request = self.context['request']
        # # 获取当前登录的用户
        # # creator = Employee.objects.filter(user=request.user).first()
        # creator = Employee.objects.filter().first()
        # apply_id = request.data['apply_id']
        # apply = Apply.objects.get(id=apply_id)
        # print request.data

        # collection_record = CollectionRecord(
            # record_type=CollectionRecord.COLLECTION,
            # object_type=validated_data['collection_type'],
            # collection_note=validated_data['collection_note'],
            # promised_repay_time=validated_data['promised_repay_time'],
            # create_by=creator,
            # apply=apply,
        # )

        # # installment_numbers = models.CharField(max_length=255, help_text="逾期期数", default="0")
        # # overdue_days = models.IntegerField(help_text="逾期天数", default=0)
        # # should_repay_amount = models.IntegerField(help_text="应还金额", default=0)
        # # ori_should_repay_amount = models.IntegerField(help_text="委案金额", default=0)
        # collection_record.save()

        # validated_data['collection_record'] = collection_record

        # record_tag = CollectionRecordTag(**validated_data)
        # record_tag.save()

        # return collection_record


    class Meta:
        model = CollectionRecordTag
        fields = (
            'id', 'call_status', 'collection_type', 'xinxiu_type', 'collection_note',
            'user_attitude', 'repay_attitude', 'promised_repay_time', 'overdue_note',
            'contactor_truth', 'contactor_attitude', 'contactor_negative_info', 'negative_info_note',
        )
        read_only = ('id', 'update_at')



class CollectionRecordSerializer(CuteSerializer):
    tag = CollectionRecordTagSerializer(many=False, read_only=True)

    def to_representation(self, obj):
        print 'in field representation'
        ori_data = super(CollectionRecordSerializer, self).to_representation(obj)
        data = ori_data
        print data

        add_time = data['create_at']
        employee = obj.create_by
        collector = employee.username if employee else ''
        notes = data['collection_note']
        record_type = obj.get_record_type_display()
        print obj
        print obj.get_record_type_display()

        # fields_data = [ImportFieldSerializer(f).data for f in fields]
        new_data = dict(
            id=data['id'],
            tag=data.get('tag', {}),
            add_time=add_time,
            collector=collector,
            notes=notes,
            report_type=record_type,
            promised_repay_time=data['promised_repay_time'],
        )
        tag_data = dict()

        installment_numbers_str = data['installment_numbers'].split(",") if data['installment_numbers'] else []
        extra_data = dict(
            overdue_installment_numbers=installment_numbers_str,
            overdue_days=data['overdue_days'],
            should_repay_amount=data['should_repay_amount'],
            collection_amount=data['ori_should_repay_amount'],
        )

        data = new_data
        print data
        data.update(dict(extra=extra_data))
        # data.update(dict(tag=tag_data))
        return data

    def create(self, validated_data):
        """creator: 从 request 中获取, fields 嵌套数据, 独立处理"""

        print 'in create'
        print validated_data
        request = self.context['request']
        serializer = CollectionRecordTagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        print validated_data
        print serializer
        validated_data = serializer.validated_data
        print '88888888888' * 10
        if not validated_data:
            msg = u'合法数据为空.'
            print msg
            print self.context['request'].data
            raise serializers.ValidationError(msg)

        # 获取当前登录的用户
        creator = Employee.objects.filter(user=request.user).first()
        # creator = Employee.objects.filter().first()
        apply_id = request.data['apply_id']
        apply = Apply.objects.get(id=apply_id)
        print request.data

        if apply.employee != creator:
            msg = u'您没有为该订单添加催记权限，请先分配.'
            raise APIException(msg)

        collection_record_data = dict(
            record_type=CollectionRecord.COLLECTION,
            object_type=validated_data['collection_type'],
            collection_note=validated_data['collection_note'],
            promised_repay_time=validated_data.get('promised_repay_time'),
            create_by=creator,
            apply=apply,
        )
        extra_data = collection_extra_data(apply)
        collection_record_data.update(extra_data)
        collection_record = CollectionRecord(**collection_record_data)
        collection_record.save()

        validated_data['collection_record'] = collection_record

        record_tag = CollectionRecordTag(**validated_data)
        record_tag.save()

        return collection_record



    class Meta:
        model = CollectionRecord
        # fields = ('id', 'name', 'status', 'update_at', 'fields')
        fields = (
            'id', 'create_at', 'create_by', 'collection_note', 'promised_repay_time', 'record_type', 'installment_numbers',
            'overdue_days', 'should_repay_amount', 'ori_should_repay_amount',
            'tag'
        )
        # extra_kwargs = {'id': {'read_only': True}}
        read_only_fields = fields


class QualitySerializer(serializers.ModelSerializer):
    employee = serializers.SlugRelatedField(slug_field='username', read_only=True)
    quality_people = serializers.SlugRelatedField(slug_field='username', read_only=True)
    inspection_detail = serializers.SlugRelatedField(slug_field='cn_name', read_only=True)

    class Meta:
        model = QualityControlRecord
        fields = (
            'id', 'cn_group', 'order_number', 'customer_phone', 'employee', 'treatment',
            'recording_time', 'inspection_detail', 'quality_people', 'customer'
        )

    def to_representation(self, instance):
        data = super(QualitySerializer, self).to_representation(instance)
        data['recording_time'] = data['recording_time'].replace("T", " ")
        return data
