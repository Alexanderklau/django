# -*- coding: utf-8 -*-
import json

from rest_framework import serializers

from business_manager.config_center.models import ProfileField, ProfileModule
from business_manager.import_data.models import ImportModule, ImportField
# from business_manager.import_data.services import update_attr
# from business_manager.config_center.models import ProfileModule

from business_manager.employee.models import get_employee_platform
from business_manager.employee.models import Employee


def update_attr(instance, update_data):
    for k, v in update_data.items():
        v = v or getattr(instance, k)
        setattr(instance, k, v)


def get_request_data(request):
    data = request.data.get('data') if request.data.get('data') else request.data
    if len(data) == 1:
        for k,v in data.items():
            if not v:
                data = json.loads(k)
                data = data.get('data') if data.get('data') else data

    return data




class CuteSerializer(serializers.ModelSerializer):
    """feature

    1.动态指定 fields
    """

    # def __init__(self, *args, **kwargs):
        # # Don't pass the 'fields' arg up to the superclass

        # # Instantiate the superclass normally
        # super(CuteSerializer, self).__init__(*args, **kwargs)

        # fields = self.get_cute_fields()

        # if fields is not None:
            # # Drop any fields that are not specified in the `fields` argument.
            # allowed = set(fields)
            # existing = set(self.fields.keys())
            # for field_name in existing - allowed:
                # self.fields.pop(field_name)


    def is_retrieve(self, view):
        """通过有没有 lookup_field 判断"""
        lookup_url_kwarg = view.lookup_url_kwarg or view.lookup_field
        pk = view.kwargs.get(lookup_url_kwarg)

        return True if pk else False

    def get_method(self, request, is_retrieve=False):
        """http 方法, 转换为 viewset 方法"""

        ori_method = request.method.lower()
        method_dic = {
            'post': 'create',
            'put': 'update',
            'get': 'list',
        }
        method = method_dic.get(ori_method)
        if method == 'list' and is_retrieve:
            method = 'retrieve'

        return method

    def get_cute_fields(self):
        print 'in get_cute_fields'

        request = self.context.get('request')
        if not request:
            return
        view = self.context.get('view')
        is_retrieve = self.is_retrieve(view)

        method_field_format = 'cute_{}_fields'
        method = self.get_method(request, is_retrieve)
        if not method:
            return

        method_field_str = method_field_format.format(method)
        fields = getattr(self.Meta, method_field_str, None)

        return fields

    # def to_representation(self, obj):
        # ori_data = super(CuteSerializer, self).to_representation(obj)
        # data = ori_data
        # create_at = data.get('create_at')
        # update_at = data.get('update_at')
        # promised_repay_time = data.get('promised_repay_time')
        # if create_at:
            # data['create_at'] = create_at.replace('T', ' ')
        # if update_at:
            # data['update_at'] = update_at.replace('T', ' ')
        # if update_at:
            # data['promised_repay_time'] = promised_repay_time.replace('T', ' ')

        # return data


# class ProfileModuleSerializer(serializers.ModelSerializer):
    # class Meta:
        # model = ProfileModule
        # fields = ('id', 'module', 'user_field_name', 'sys_field_id', 'sys_field_name')


class ImportFieldSerializer(CuteSerializer):
    # sys_field_show_name = serializers.CharField(source='sys_field_id.show_name')
    # sys_field_name = serializers.CharField(source='sys_field_id.name')

    def to_representation(self, obj):
        ori_data = super(ImportFieldSerializer, self).to_representation(obj)
        data = ori_data

        profile_field = ProfileField.objects.filter(id=ori_data['sys_field_id']).first()
        extra_data = dict(
            sys_field_show_name=profile_field.show_name,
            sys_field_name=profile_field.name,
        )
        data.update(extra_data)
        return data

    # def to_internal_value(self, data):
        # ori_data = super(ImportFieldSerializer, self).to_internal_value(data)
        # new_data = ori_data
        # module_id = data.get('module_id')
        # if module_id:
            # module = ImportModule.objects.filter(id=module_id).first




    class Meta:
        model = ImportField
        fields = ('id', 'user_field_name', 'sys_field_id')
        cute_retrieve_fields = ('id', 'sys_field_id')
        # extra_kwargs = {'id': {'read_only': False}}


class ImportModuleSerializer(CuteSerializer):
    # fields = ImportFieldSerializer(many=True)
    def to_representation(self, obj):
        print 'in field representation'
        ori_data = super(ImportModuleSerializer, self).to_representation(obj)
        data = ori_data

        fields = ImportField.objects.filter(module=obj.id, status__gte=0)
        print fields
        fields_data = [ImportFieldSerializer(f).data for f in fields]
        extra_data = dict(
            fields=fields_data
        )
        data.update(extra_data)
        return data


    def update(self, instance, validated_data):
        print 'in update'
        print validated_data
        if not validated_data:
            msg = u'合法数据为空.'
            print msg
            print self.context['request'].data
            raise serializers.ValidationError(msg)
            pass
        request = self.context['request']


        update_attr(instance, validated_data)
        instance.save()

        import_fields = ImportField.objects.filter(module=instance)
        # 每次更新 fields 对应的数据都是全量的, 所以 现将 status = -1 (删除)
        import_fields.update(status=-1)

        # fields = self.context['request'].data.get('fields', [])
        # fields = self.context['request'].data.get('data', {}).get('fields', [])
        fields = get_request_data(self.context['request']).get('fields', [])
        for field in fields:
            field_id = field.pop('id', None)
            serializer = ImportFieldSerializer(data=field)
            if not serializer.is_valid():
                msg_invalid = serializer.errors
                raise serializers.ValidationError(msg_invalid)

            if field_id:
                import_field = ImportField.objects.filter(id=field_id, module=instance)
                if import_field:
                    serializer.validated_data['status'] = 0
                    import_field.update(**serializer.validated_data)
                else:
                    msg = u"fields id '{}', 不存在.".format(field_id)
                    raise serializers.ValidationError(msg)
                    pass
            else:
                serializer.validated_data['module'] = instance
                serializer.save()
                # import_field = ImportField(**erield)
                # import_field.save()

        return instance

    def create(self, validated_data):
        """creator: 从 request 中获取, fields 嵌套数据, 独立处理"""

        print 'in create'
        print validated_data
        if not validated_data:
            msg = u'合法数据为空.'
            print msg
            print self.context['request'].data
            raise serializers.ValidationError(msg)
            pass
        request = self.context['request']

        # 获取当前登录的用户
        creator = Employee.objects.filter(user=request.user).first()
        # creator = Employee.objects.filter().first()
        platform = get_employee_platform(request).first().name
        validated_data['creator'] = creator
        validated_data['platform'] = platform

        import_module = ImportModule(**validated_data)
        import_module.save()

        # 创建 ImportField
        # fields = self.context['request'].data.get('data', {}).get('fields', [])
        fields = get_request_data(self.context['request']).get('fields', [])
        for field in fields:
            field_id = field.pop('id', None)
            serializer = ImportFieldSerializer(data=field)
            print serializer.is_valid()
            print serializer.errors

            serializer.validated_data['module'] = import_module
            serializer.save()

        return import_module

    def validate_name(self, value):
        pk = 0
        if self.instance:
            pk = self.instance.id
        platform = get_employee_platform(self.context['request']).values_list('name', flat = True)
        import_module = ImportModule.objects.filter(name=value, status__gte=0, platform__in=platform).exclude(id=pk).first()
        if import_module:
            msg = u"模板名 '{}', 已存在.".format(value)
            raise serializers.ValidationError(msg)

        return value

    class Meta:
        model = ImportModule
        # fields = ('id', 'name', 'status', 'update_at', 'fields')
        fields = ('id', 'name', 'status', 'update_at')
        extra_kwargs = {'id': {'read_only': True}}


class ImportModuleListSerializer(CuteSerializer):

    class Meta:
        model = ImportModule
        # fields = ('id', 'name', 'status', 'update_at', 'fields')
        fields = ('id', 'name', 'status', 'update_at', 'module_type')


