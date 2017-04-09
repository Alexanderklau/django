#!/usr/bin/env python
# coding=utf-8
import json

from django.core.management.base import BaseCommand
from django.db import connection

from business_manager.order.apply_models import InfoModule
from business_manager.import_data.models import ImportModule, ImportField
from business_manager.config_center.models import ProfileField, ProfileModule

INIT_MODEULS = [
    {"cn_name": u"个人信息", "field_name": u"用户名"},
    {"cn_name": u"个人信息", "field_name": u"手机"},
    {"cn_name": u"个人信息", "field_name": u"座机"},
    {"cn_name": u"个人信息", "field_name": u"传真"},
    {"cn_name": u"个人信息", "field_name": u"身份证"},
    {"cn_name": u"个人信息", "field_name": u"地址"},
    {"cn_name": u"个人信息", "field_name": u"邮箱"},
    {"cn_name": u"个人信息", "field_name": u"qq"},
    {"cn_name": u"个人信息", "field_name": u"微信"},
    {"cn_name": u"个人信息", "field_name": u"微博"},
    {"cn_name": u"个人信息", "field_name": u"加入的qq群号"},
    {"cn_name": u"重要联系人信息", "field_name": u"重要联系人电话"},
    {"cn_name": u"重要联系人信息", "field_name": u"重要联系人身份证"},
    {"cn_name": u"重要联系人信息", "field_name": u"重要联系人地址"},
    {"cn_name": u"收货人信息", "field_name": u"收货人姓名"},
    {"cn_name": u"收货人信息", "field_name": u"收货人电话"},
    {"cn_name": u"收货人信息", "field_name": u"收货人地址"},
    {"cn_name": u"公司信息", "field_name": u"公司"},
    {"cn_name": u"公司信息", "field_name": u"公司地址"},
    {"cn_name": u"公司信息", "field_name": u"公司电话"},
    {"cn_name": u"联系人信息", "field_name": u"联系人电话"},
    {"cn_name": u"联系人信息", "field_name": u"联系人身份证"},
    {"cn_name": u"联系人信息", "field_name": u"联系人地址"},
    {"cn_name": u"联系人信息", "field_name": u"联系人工作单位"},
    {"cn_name": u"最近出现时间", "field_name": u"最近出现时间"},
]

INIT_PROFILE_FIELOD = [
    {"name": "string_xinxiu_update_at", "show_name": "信修__最近出现时间", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "最近出现时间"},
    {"name": "string_xinxiu_contact_company", "show_name": "信修__联系人公司", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "联系人工作单位"},
    {"name": "string_xinxiu_contact_addr", "show_name": "信修__联系人地址", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "联系人地址"},
    {"name": "string_xinxiu_contact_id_no", "show_name": "信修__联系人身份证", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "联系人身份证"},
    {"name": "string_xinxiu_contact_phone", "show_name": "信修__联系人电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "联系人电话"},
    {"name": "string_xinxiu_company", "show_name": "信修__单位名称", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "公司"},
    {"name": "string_xinxiu_company_addr", "show_name": "信修__单位地址", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "公司地址"},
    {"name": "string_xinxiu_company_phone", "show_name": "信修__单位电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "公司电话"},
    {"name": "string_xinxiu_shopping_addr", "show_name": "信修__收货地址", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "收货人地址"},
    {"name": "string_xinxiu_shopping_phone", "show_name": "信修__收货电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "收货人电话"},
    {"name": "string_xinxiu_shopping_name", "show_name": "信修__收货姓名", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "收货人姓名"},
    {"name": "string_xinxiu_important_contact_addr", "show_name": "信修__重要联系人地址", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "重要联系人电话"},
    {"name": "string_xinxiu_important_contact_id_no", "show_name": "信修__重要联系人身份证", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "重要联系人身份证"},
    {"name": "string_xinxiu_important_contact_phone", "show_name": "信修__重要联系人电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "重要联系人地址"}, 
    {"name": "string_xinxiu_qq_group", "show_name": "信修__QQ群", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "加入的qq群号", "br_name": "QQ群(百融匹配)"},
    {"name": "string_xinxiu_weibo", "show_name": "信修__微博", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "微博", "br_name": "微博(百融匹配)"},
    {"name": "string_xinxiu_wechat", "show_name": "信修__微信", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "微信"},
    {"name": "string_xinxiu_qq", "show_name": "信修__QQ", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "qq"},
    {"name": "string_xinxiu_email", "show_name": "信修__电子邮箱", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "邮箱", "br_name": "邮箱(百融匹配)"},
    {"name": "string_xinxiu_family_addr", "show_name": "信修__家庭地址", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "地址", "br_name": "地址(百融匹配)"},
    {"name": "string_xinxiu_id_no", "show_name": "信修__身份证号码", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "身份证"},
    {"name": "string_xinxiu_fax", "show_name": "信修__传真", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "传真"},
    {"name": "string_xinxiu_telephone", "show_name": "信修__固定电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "座机"},
    {"name": "string_xinxiu_phone", "show_name": "信修__电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "手机"},
    {"name": "string_xinxiu_name", "show_name": "信修__名字", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "用户名"},
    {"name": "string_xinxiu_ourphone", "show_name": "信修__我方提供通电话", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "提供手机号", "br_name": "手机(原始数据)"},
    {"name": "string_xinxiu_our_idno", "show_name": "信修__我方提供通身份证", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "提供身份证", "br_name": "身份证(原始数据)"},
    {"name": "string_xinxiu_channel", "show_name": "信修__贷款渠道", "is_innner": 1, "type": "textview", "platform": "rst", "td_name": "数据来源姓名", "br_name": "渠道(原始数据)"},
    # 特殊处理字段
    {"name": "string_xinxiu_social_phone", "show_name": "信修__社会关系", "is_innner": 1, "type": "textview", "platform": "rst", "br_name": "社会关系(百融匹配)"},
    {"name": "string_xinxiu_bairong_phone", "show_name": "信修__百融电话", "is_innner": 1, "type": "textview", "platform": "rst", "br_name": "手机(百融匹配)"},
    {"name": "string_xinxiu_bairong_telephone", "show_name": "信修__百融固定电话", "is_innner": 1, "type": "textview", "platform": "rst", "br_name": "固话(百融匹配)"},
]


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        if args[0] == 'add_record':
            for item in INIT_MODEULS:
                InfoModule.objects.create(**item)
        elif args[0] == 'init_table':
            self.create_table()
        elif args[0] == 'init_field':
            self.init_import_module()

    def create_table(self):
        sql1 = "CREATE TABLE `info_module` ( \
                `id` int(11) NOT NULL AUTO_INCREMENT, \
                `cn_name` varchar(512) DEFAULT '', \
                `field_name` varchar(512) DEFAULT '', \
                PRIMARY KEY (`id`) \
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8"
        sql2 = "CREATE TABLE `info_field` (\
                `id` int(11) NOT NULL AUTO_INCREMENT,\
                `cn_name` varchar(512) NOT NULL,\
                `content` varchar(1024) DEFAULT '',\
                `status` int(11) DEFAULT '2',\
                `user_id` int(11) NOT NULL,\
                `info_module` varchar(512) DEFAULT '默认',\
                `is_must` tinyint(1) DEFAULT '0',\
                PRIMARY KEY (`id`)\
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8"
        sql3 = "CREATE TABLE `repair_history` (\
                `id` int(11) NOT NULL AUTO_INCREMENT,\
                `operation_time` datetime DEFAULT NULL,\
                `employee_id` int(11) NOT NULL,\
                `operation_status` int(11) NOT NULL,\
                `info_field_id` int(11) NOT NULL\
                PRIMARY KEY (`id`)\
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8"
        with connection.cursor() as cursor:
            cursor.execute(sql1)
            cursor.execute(sql2)
            cursor.execute(sql3)

    def init_import_module(self):
        """
        添加信修字段
        """
        profile_field = []
        td, br = self.create_import_module()
        for item in INIT_PROFILE_FIELOD:
            pro = ProfileField.objects.create(name=item['name'], show_name=item['show_name'], is_inner=1, type='textview', platform=item['platform'])
            if item.get('td_name'):
                self.create_import_module_field(pro, item['td_name'], td)
            if item.get('br_name'):
                self.create_import_module_field(pro, item['br_name'], br)
            profile_field.append(pro)
        ids = [{'field_id': item.id, 'is_must': 0} for item in profile_field]
        import_module = ProfileModule.objects.filter(show_name='import').first()
        optional_fields = json.loads(import_module.required_fields)
        import_module.required_fields = json.dumps(optional_fields + ids)
        import_module.save()

    def create_import_module(self):
        name = u"同盾-信修"
        td = ImportModule.objects.create(name=name, status=0, creator_id=1, module_type='b', platform='rst')
        br = ImportModule.objects.create(name=u"百融-信修", status=0, creator_id=1, module_type='b', platform='rst')
        return td, br

    def create_import_module_field(self, sys_field, cn_name, module):
        ImportField.objects.create(module=module, user_field_name=cn_name, sys_field_id=sys_field, platform='rst', status=0)
