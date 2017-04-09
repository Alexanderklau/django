#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand
from business_manager.employee.models import *

class Command(BaseCommand):
    def init_review_permission(self):
        p_set = PermissionSet(name = u'查看审批订单', belong_system_name = u'审批系统', belong_sub_name = u'所有审批',
                             permissions = '/review/all,/review/info/view,/review/all_review_json,/employee/get_all_employee_group,\
                              /employee/search_employee,/review/all_orders')
        p_set.save()

        p_set = PermissionSet(name = u'审核权限', belong_system_name = u'审批系统', belong_sub_name = u'我的审批',
                             permissions = '/review/mine,/review/info,/review/action,/review/my_review_json,/review/upload_info,\
                              /employee/get_all_employee_group,/employee/search_employee,/review/my_orders,/review/all_orders')
        p_set.save()

        p_set = PermissionSet(name = u'审批BI查看(个人)', belong_system_name = u'审批系统', belong_sub_name = u'',
                             permissions = '/review/mine,/review/my_review_json')
        p_set.save()

        p_set = PermissionSet(name = u'审批BI查看(主管)', belong_system_name = u'审批系统', belong_sub_name = u'',
                             permissions = '/review/mine,/review/my_review_json,/employee/search_employee')
        p_set.save()

    def init_operation_permission(self):
        p_set = PermissionSet(name = u'代扣订单', belong_system_name = u'运营系统', belong_sub_name = u'代扣订单',
                             permissions = '/operation')
        p_set.save()
        p_set = PermissionSet(name = u'运营BI查看(个人)', belong_system_name = u'运营系统', belong_sub_name = u'',
                             permissions = '/operation')
        p_set.save()
        p_set = PermissionSet(name = u'运营BI查看(主管)', belong_system_name = u'运营系统', belong_sub_name = u'',
                             permissions = '/operation,/employee/search_employee')
        p_set.save()
        p_set = PermissionSet(name = u'查看运营订单', belong_system_name = u'运营系统', belong_sub_name = u'代扣订单',
                             permissions = '/operation/repay,/operation/repay_loan_json')
        p_set.save()
        p_set = PermissionSet(name = u'代付订单', belong_system_name = u'运营系统', belong_sub_name = u'代付订单',
                             permissions = '/operation')
        p_set.save()

    def init_collect_permission(self):
        p_set = PermissionSet(name = u'分配订单', belong_system_name = u'催收系统', belong_sub_name = u'所有催收',
                             permissions = '/collection/collection_type/,/collection/action/user_info/,/collection/all,/collection/action/change,/collection/all_collection_json,/collection/modal/dispatch,/collection/get_employee_info')
        p_set.save()
        p_set = PermissionSet(name = u'查看逾期订单', belong_system_name = u'催收系统', belong_sub_name = u'所有催收',
                             permissions = '/collection/all,/collection/all_collection_json,/collection/info,/collection/get_collection_record_json')
        p_set.save()
        p_set = PermissionSet(name = u'逾期订单催收', belong_system_name = u'催收系统', belong_sub_name = u'我的催收',
                             permissions = '/collection/mine,/collection/info,/collection/action/add,/collection/action/finish,/collection/action/do_repay_loan,\
                              /collection/all_collection_json,/collection/get_collection_record_json,/collection/action/add_collection_record,\
                              /collection/action/fileupload,/collection/action/sendmessage')
        p_set.save()
        p_set = PermissionSet(name = u'催收BI查看(个人)', belong_system_name = u'催收系统', belong_sub_name = u'',
                             permissions = '')
        p_set.save()
        p_set = PermissionSet(name = u'催收BI查看(主管)', belong_system_name = u'催收系统', belong_sub_name = u'',
                             permissions = '/collection,/employee/search_employee')
        p_set.save()
        p_set = PermissionSet(name = u'数据导入', belong_system_name = u'催收系统', belong_sub_name = u'数据导入',
                             permissions = '/collection,/import')
        p_set.save()

    def init_audit_permission(self):
        p_set = PermissionSet(name = u'导出应收报表', belong_system_name = u'财务系统', belong_sub_name = u'应收账单',
                             permissions = '/audit/download_receivable_table,/audit/receivables,/audit/receivables_json')
        p_set.save()
        p_set = PermissionSet(name = u'导出实收报表', belong_system_name = u'财务系统', belong_sub_name = u'实收账单',
                             permissions = '/audit/received,/audit/download_received_table,/audit/received_json')
        p_set.save()
        p_set = PermissionSet(name = u'查看实收账单', belong_system_name = u'财务系统', belong_sub_name = u'实收账单',
                             permissions = '/audit/received,/audit/received_json')
        p_set.save()
        p_set = PermissionSet(name = u'查看应收账单', belong_system_name = u'财务系统', belong_sub_name = u'应收账单',
                             permissions = '/audit/receivables,/audit/receivables_json')
        p_set.save()
        p_set = PermissionSet(name = u'财务BI查看', belong_system_name = u'财务系统', belong_sub_name = u'',
                             permissions = '/audit')
        p_set.save()
        p_set = PermissionSet(name = u'财务复核', belong_system_name = u'财务系统', belong_sub_name = u'财务复核',
                             permissions = '/audit/check_repay_json,/audit/info/check,/audit/action/do_back_check,/audit/action/do_confirm_check,/audit/check')
        p_set.save()

    def init_custom_permission(self):
        p_set = PermissionSet(name = u'查看订单', belong_system_name = u'客服中心', belong_sub_name = '',
                             permissions = '')
        p_set.save()

    def init_employee_permission(self):
        p_set = PermissionSet(name = u'新增员工', belong_system_name = u'员工系统', belong_sub_name = u'新增员工',
                             permissions = '/employee/new_employee,/employee/search_employee,/employee/employee_statistic,/employee/get_all_employee_group')
        p_set.save()
        p_set = PermissionSet(name = u'编辑员工', belong_system_name = u'员工系统', belong_sub_name = u'员工维护',
                             permissions = '/employee/new_employee,/employee/search_employee,/employee/employee_statistic,/employee/get_all_employee_group,/employee/get_employee_info,/employee/modify_employee')
        p_set.save()

    def init_neworder_permission(self):
        p_set = PermissionSet(name = u'创建订单', belong_system_name = u'进件系统', belong_sub_name = u'新增订单',
                             permissions = '/pc_reg,/employee/search_employee')
        p_set.save()
        
        p_set = PermissionSet(name = u'查看订单', belong_system_name = u'进件系统', belong_sub_name = u'订单列表',
                             permissions = '/new_order/all_apply_list,/order/all,/order/all_json,/review/info/view,/employee/search_employee')
        p_set.save()

    def init_config_permission(self):
        p_set = PermissionSet(name = u'子系统配置', belong_system_name = u'配置系统', belong_sub_name = u'子系统配置',
                             permissions = '/config_center')
        p_set.save()
        p_set = PermissionSet(name = u'编辑用户组', belong_system_name = u'配置系统', belong_sub_name = u'用户组与权限',
                             permissions = '/employee')
        p_set.save()
        p_set = PermissionSet(name = u'贷款策略配置', belong_system_name = u'配置系统', belong_sub_name = u'贷款策略配置',
                             permissions = '/strategy')
        p_set.save()

    
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


    def handle(self, *args, **kwargs):
        self.init_review_permission()
        self.init_operation_permission()
        self.init_collect_permission()
        self.init_audit_permission()
        self.init_custom_permission()
        self.init_employee_permission()
        self.init_neworder_permission()
        self.init_config_permission()
        self.create_super_admin()
