#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand
from business_manager.employee.models import *

class Command(BaseCommand):
    def create_super_admin(self):
        group = EmployeeGroup(group_name = u'超级管理员', is_editable = 0, platform = 'saas_test')
        group.save()

        permission_list = PermissionSet.objects.filter()
        for p in permission_list:
            group.permissions.add(p)
    
        #p_set = PermissionSet.objects.get(name = u'创建订单')
        #group.permissions.add(p_set)
        #p_set = PermissionSet.objects.get(name = u'查看订单')
        #group.permissions.add(p_set)
        #p_set = PermissionSet.objects.get(name = u'新增员工')
        #group.permissions.add(p_set)
        #p_set = PermissionSet.objects.get(name = u'编辑员工')
        #group.permissions.add(p_set)
        #p_set = PermissionSet.objects.get(name = u'编辑用户组')
        #group.permissions.add(p_set)
        #p_set = PermissionSet.objects.get(name = u'子系统配置')
        #group.permissions.add(p_set)
    
        group.save()
    
        create_employee("admin", "admin@rst.com", "13928449141", u"超级管理员", 'other', [group], 'saas_test')

