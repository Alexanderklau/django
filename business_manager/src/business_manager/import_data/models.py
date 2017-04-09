# -*- coding:utf-8 -*-
import uuid
from django.db import models
from business_manager.order.models import User
from business_manager.employee.models import Employee
from business_manager.config_center.models import WorkFlow, ProfileField

# Create your models here.


class UploadFile(models.Model):

    UPLOAD_FILE = 0
    FAILED_FILE = 1
    UNAVAILABLE = 2

    upload_file_choice = (
        (UPLOAD_FILE, u"上传文件"),
        (FAILED_FILE, u"失败文件"),
        (UNAVAILABLE , u"不可用文件"),
    )

    creator = models.ForeignKey(Employee, null=True, help_text='上传员工')
    file_name = models.CharField(max_length=64, help_text='文件名')
    upload_file = models.FileField(help_text='上传文件', upload_to=u"upload_file/%Y/%m/%d")
    upload_time = models.DateTimeField(auto_now_add=True, help_text='上传时间')
    status = models.IntegerField(default=UPLOAD_FILE, choices=upload_file_choice,
                                 help_text='文件类型(上传文件，导入失败文件)')
    download_url = models.CharField(max_length=1024, null=True)

    class Meta:
        db_table = "upload_file"


VALID = 0
READ_ONLY = 1
USING = 2
LATEST_USE = 3
INVALID = 4
# 如果有使用到, 则 Valid = 未启用
ACTIVE = 5

DELETE = -1
# 临时数据, 可以删除, 对用户不可见
TEMP = -2
status_choices = (
    (VALID, u"正常"),
    (READ_ONLY, u"只读"),
    (USING, u"使用中"),
    (LATEST_USE, u"最后一次使用"),
    (INVALID, u"禁用"),
    (ACTIVE, u"启用"),

    (DELETE, u"删除"),
    (TEMP, u"临时"),
)


class ImportModule(models.Model):
    """数据导入模板, 包含用户上传表头 与 系统预置字段 的对应关系"""

    IMPORT_DATA = "a"
    REPAIR_MSG = "b"
    IMPORT_CONTACT = "c"

    module_choices = (
        (IMPORT_DATA, u"导入数据"),
        (REPAIR_MSG, u"催收信修"),
        (IMPORT_CONTACT, u"导入联系人"),
    )

    IS_ACTIVE = 1
    NOT_ACTIVE = 0

    active_choices = (
        (IS_ACTIVE, u"启用"),
        (NOT_ACTIVE, u"未启用")
    )

    name = models.CharField(max_length=64, null=True, help_text="模板名称")

    platform = models.CharField(max_length = 64, blank = True)
    product = models.CharField(max_length = 64, blank = True)

    status = models.IntegerField(default=0, choices=status_choices, help_text="模板状态")
    # is_in_use = models.BooleanField(default=False, help_text="最后一次使用的模板")
    creator = models.ForeignKey(Employee)
    update_at = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)

    module_type = models.CharField(choices=module_choices, default=IMPORT_DATA, max_length=64)
    # is_active = models.IntegerField(choices=active_choices, default=NOT_ACTIVE)

    class Meta:
        db_table = u'import_module'

    def __unicode__(self):
        return u'%d)%s' % (self.id, self.name)


class ImportField(models.Model):
    """用户上传表头 与 系统预置字段 的对应关系"""
    module = models.ForeignKey(ImportModule, related_name='fields')
    user_field_name = models.CharField(max_length=64, help_text="表头名称")
    sys_field_id = models.ForeignKey(ProfileField)
    sys_field_name = models.CharField(max_length=64, help_text="预置字段名称")

    platform = models.CharField(max_length = 64, blank = True)
    product = models.CharField(max_length = 64, blank = True)

    status = models.IntegerField(default=0, choices=status_choices, help_text="状态")
    update_at= models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'import_module_field'

    def __unicode__(self):
        return u'%d)%s -> %s' % (self.id, self.user_field_name, self.sys_field_name)


class ParseFileRecord(models.Model):
    """
    文件和模板对映关系
    """
    PARSING = 11
    WAIT_PARSE = 13
    IN_PARSE_QUEUE = 14

    # 终态
    PARSED_COMPLETE = 0
    PARSED_FAILED = 12
    HEADER_MATCH_ERROR = 15
    # PARSED_ERROR = 16
    # PARTIAL_SUCCESS = 17

    # 终态数据在数据库里取
    FINAL_STATE = (
        PARSED_COMPLETE,
        PARSED_FAILED,
        # PARSED_ERROR,
        HEADER_MATCH_ERROR,
        # PARTIAL_SUCCESS,
    )

    parse_status = (
        (PARSING, u'解析中'),
        (WAIT_PARSE, u'等待解析'),
        (PARSED_COMPLETE, u'解析完成'),
        (PARSED_FAILED, u'解析失败'),
        (IN_PARSE_QUEUE, u'解析队列中'),
        (HEADER_MATCH_ERROR, u'表头匹配失败'),
    )

    creator = models.ForeignKey(Employee, help_text='创建人')
    file = models.ForeignKey(UploadFile, help_text="文件")
    module = models.ForeignKey(ImportModule, help_text="模板")
    status = models.IntegerField(choices=parse_status, default=WAIT_PARSE, help_text="解析状态")
    create_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    total_count = models.IntegerField(default=0, help_text="数据总条数")
    success_count = models.IntegerField(default=0, help_text="数据导入成功条数")
    fail_count = models.IntegerField(default=0, help_text="数据导入失败条数")
    fail_file = models.ForeignKey(UploadFile, related_name="fail_file", null=True, help_text="数据导入失败文件")

    class Meta:
        db_table = "parse_file_record"
