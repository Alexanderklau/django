# -*- coding:utf-8 -*-

# Create your views here.
import sys
import time
reload(sys) 
sys.setdefaultencoding("utf-8") 
from business_manager.import_data.models import UploadFile
from business_manager.util.import_file_util import ImportFile
from business_manager.util.import_file_util import ImportFileException
from business_manager.util.common_response import ImportResponse
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt

from rest_framework import exceptions, status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route

from business_manager.employee.models import Employee
from business_manager.config_center.models import ProfileField, ProfileModule
from business_manager.import_data.models import ImportModule, ImportField
from business_manager.import_data.serializers import ImportModuleSerializer, ImportFieldSerializer, ImportModuleListSerializer
from business_manager.import_data.services import CuteViewSet
from business_manager.import_data.services import import_field_inner, repayment_create_or_update, update_attr, get_request_data
from business_manager.import_data.models import ParseFileRecord, USING, READ_ONLY
from business_manager.import_data.parse_file import parse_file, get_parse_progress
from business_manager.import_data.tasks import process_parse_file
from business_manager.employee.models import get_employee_platform


MAX_FILE_SIZE = 5 * 1024 ** 2   # 5M


@csrf_exempt
def header_match(request):
    if request.method != 'POST':
        return ImportResponse.failed(msg='wrong method')
    header_files = request.FILES
    if not header_files:
        return ImportResponse.failed(msg="haven't post file")
    header_file = header_files['data']
    # determine the file size
    if not header_file.size or header_file.size > MAX_FILE_SIZE:
        return ImportResponse.failed(msg="file limit exceeded")

    try:
        import_file = ImportFile(header_file)
        header = import_file.header
        # header = ['"%s"' % item for item in header]
    except ImportFileException as e:
        print('header_math error: %s' % e)
        return ImportResponse.failed(msg=e.msg)
    return ImportResponse.success(data=header, msg='success')


@csrf_exempt
def post_file(request):

    if request.method == 'POST':
        print request.FILES
        print request.POST
        files_ = request.FILES
        # check parameters
        if not files_:
            return ImportResponse.failed(msg="haven't post file")
        file_ = files_['data']
        if not file_.size:
            return ImportResponse.failed(msg="parameters error")
        # determine the file size
        if file_.size > MAX_FILE_SIZE:
            return ImportResponse.failed(msg="file limit exceeded")
        module_id = request.POST.get("module_id")

        if module_id < 0:
            return ImportResponse.failed(msg="module_id is not available")

        module = ImportModule.objects.filter(id=module_id).first()
        if not module:
            return ImportResponse.failed(msg="module not found")
        # user = request.user
        # employee = Employee.objects.filter(user=user).first()
        employee = Employee.objects.filter(user=request.user).first()
        if not employee:
            return ImportResponse.failed(msg="non activated employee")
        file_id = request.POST.get('file_id')
        if file_id:  # re upload file
            file_id_list = file_id.split(",")
            reload_files = UploadFile.objects.filter(id__in=file_id_list)
            if not reload_files:
                return ImportResponse.failed(msg="unavailable file_id")
            for reload_file in reload_files:
                reload_file.status = UploadFile.UNAVAILABLE
                reload_file.save()
                temp_record = ParseFileRecord.objects.filter(file=reload_file).first()
                if temp_record:
                    temp_record.delete()
            # temp_file.file_name = file_.name
            # temp_file.upload_file = file_
            # temp_file.save()
        print("------------")
        print(file_.name)
        file_type = file_.name.split(".")[-1]
        tmp_name = str(int(time.time() * 100)) +'.' + file_type
        real_name = file_.name
        file_.name = tmp_name
        temp_file = UploadFile(creator=employee, file_name=real_name, upload_file=file_)
        temp_file.save()
        file_record = ParseFileRecord(file=temp_file, module=module, creator=employee)
        file_record.save()

        module.status = 2
        module.save()
        return ImportResponse.success(data={'file_id': temp_file.id}, msg="success")
    elif request.method == 'GET':
        # user = request.user
        # employee = Employee.objects.filter(user=user).first()
        employee = Employee.objects.filter(user=request.user).first()
        if not employee:
            return ImportResponse.failed(msg="non activated employee")
        parse_records = ParseFileRecord.objects.filter(creator=employee, status=ParseFileRecord.WAIT_PARSE)
        if not parse_records:
            return ImportResponse.failed(msg="don't have wait parse file")
        for record in parse_records:
            record.status = ParseFileRecord.IN_PARSE_QUEUE
            record.save()
            # asynchronous call
            platform = get_employee_platform(request)[0].name
            process_parse_file.delay(record.id, platform)
            # parse_file(record.id, platform)
        data = [
            {
                "file_id": item.file.id,
                "file_name": item.file.file_name,
                "upload_time": item.file.upload_time,
                "status": item.status
            } for item in parse_records
            ]
        return ImportResponse.success(data=data, msg="success")
    else:
        return ImportResponse.failed(msg="wrong method")


def delete_file(request):
    file_id = request.GET.get('file_id')
    if not file_id:
        return ImportResponse.failed(msg="None file_id")
    file_id_list = file_id.split(",")
    reload_files = UploadFile.objects.filter(id__in=file_id_list)
    if not reload_files:
        return ImportResponse.failed(msg="unavailable file_id")
    for reload_file in reload_files:
        reload_file.status = UploadFile.UNAVAILABLE
        reload_file.save()
        temp_records = ParseFileRecord.objects.filter(file=reload_file)
        for temp_record in temp_records:
            temp_record.delete()
    else:
        return ImportResponse.success(data="success", msg="success")


@csrf_exempt
def get_import_file_progress(request):
    if request.method != 'GET':
        return ImportResponse.failed(msg='wrong method')
    # user = request.user
    # employee = Employee.objects.filter(user=user).first()
    employee = Employee.objects.filter(user=request.user).first()
    if not employee:
        return ImportResponse.failed(msg="non activated employee")
    parse_records = ParseFileRecord.objects.filter(creator=employee)
    data = []
    host_name = request.META['HTTP_HOST']
    for record in parse_records:
        if record.status in ParseFileRecord.FINAL_STATE:
            print("FINAL_STATE: %s, record id: %s" % (record.status, record.id))
            success_count = record.success_count
            fail_count = record.fail_count
        else:
            print("redis state: %s, record id: %s" % (record.status, record.id))
            ret = get_parse_progress(record.id)
            print("ret: ", ret)
            success_count = ret["success_count"]
            fail_count = ret["fail_count"]
        fail_file = record.fail_file
        if fail_file:
            # fail_file_url = "http://" + host_name + '/' + fail_file.upload_file.url
            fail_file_url = fail_file.download_url
        else:
            fail_file_url = ""
        data.append({
            "file_id": record.file.id,
            "file_name": record.file.file_name,
            "upload_time": record.file.upload_time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": record.status,
            "total_count": record.total_count,
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_file_url": fail_file_url,
            "module_id": record.module.id,
            "module_name": record.module.name
        })
    return ImportResponse.success(data=data, msg='success')


@csrf_exempt
def reparse_file(request):
    if request.method != 'GET':
        return ImportResponse.failed(msg='wrong method')
    record_id = request.GET['record_id']
    parse_record = ParseFileRecord.objects.filter(id=record_id).first()
    if not parse_record:
        return ImportResponse.failed(msg='not found record')
    parse_record.status = ParseFileRecord.IN_PARSE_QUEUE
    parse_record.save()
    # asynchronous call
    platform = get_employee_platform(request)[0].name
    process_parse_file.delay(parse_record.id, platform)
    return ImportResponse.success(
        msg='success',
        data={
            "file_id": parse_record.file.id,
            "file_name": parse_record.file.file_name,
            "upload_time": parse_record.file.upload_time,
            "status": parse_record.status
        }
    )


class ImportModuleViewSet(CuteViewSet):

    serializer_class = ImportModuleSerializer
    # serializer_class_retrieve = ImportModuleRetrieveSerializer
    serializer_class_list = ImportModuleListSerializer
    queryset = ImportModule.objects.all()

    def destroy(self, request, *args, **kwargs):
        """删除: 将 instance 状态 修改为 -1 (< 0 表示用户不可见)"""
        instance = self.get_object()
        if instance.status in [USING]:
            # return Response(status=status.HTTP_204_NO_CONTENT,data=0)
            data = dict(
                code=1,
                msg=u'{} 模板在使用中, 不能删除'.format(instance.name),
                data={},
            )
            return Response(data=data)

        return super(ImportModuleViewSet, self).destroy(request, *args, **kwargs)



    @detail_route(methods=['post'])
    def post(self, request, pk=None):
        """"""
        print 'in method'
        print pk
        instance = self.get_object()
        print instance
        print type(instance)

        data = get_request_data(request, True)
        method = data.get('method')
        print data
        print method
        # return 
        if method == 'delete':
            # update_attr(instance, dict(status=-1))
            # instance.save()
            # return Response(status=status.HTTP_204_NO_CONTENT)
            return self.destroy(request)#, *args, **kwargs)
        if method == 'update':
            print 'in update'
            return self.update(request)#, *args, **kwargs)
        data = dict(
            code=0,
            msg='',
            data={},
        )
        return Response(data)



    # def create(self, request):
        # creator = Employee.objects.filter(user=request.user).first().id
        # request.data['creator'] = creator
        # print request
        # print request.data
        # return super(ImportModuleViewSet, self).create(request)


class ImportFieldViewSet(CuteViewSet):

    serializer_class = ImportFieldSerializer
    queryset = ImportField.objects.all()


    @list_route()
    def inner(self, request):
        """预置字段"""
        # data = {
            # 'int32_amount': 2000000,
            # 'int32_installment_count': 12,
            # 'string_order_number': '',
            # 'string_idcard_no': '452131199606160321',
            # 'string_bank_card_id': '6217857000029053129',
            # 'string_channel': 'lupeng',
        # }
        # repayment_create_or_update(data)
        print request
        print request.user
        queryset = ProfileModule.objects.all()
        inner_data = import_field_inner(queryset)

        code = 0
        msg = ''
        if not inner_data:
            code = 1
            msg = '没有找到对应数据'

        data = dict(
            code=code,
            msg=msg,
            data=inner_data
        )

        return Response(data)

    @list_route()
    def map(self, request):
        """匹配 用户上传表头 和 预置字段 的匹配关系"""

        # 用户上传字段
        field_names_str = request.query_params.get('field_names', '')
        field_names = field_names_str.replace(' ', '').split(',')

        # 预置字段
        queryset = ProfileModule.objects.all()
        inner_data = import_field_inner(queryset)
        inner_data_dic = {d['show_name']: d for d in inner_data}
        inner_names = inner_data_dic.keys()

        field_data = []
        for fn in field_names:
            if fn in inner_data_dic:
                inner_d = inner_data_dic[fn]
                fn_dic = dict(
                    sys_field_name=inner_d['show_name'],
                    sys_field_id=inner_d['id'],
                    user_field_name=fn,
                )
                field_data.append(fn_dic)

        code = 0
        msg = ''
        data = dict(
            code=code,
            msg=msg,
            data=field_data,
        )

        return Response(data)
