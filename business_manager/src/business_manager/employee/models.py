# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User

from django.dispatch import receiver
from django.db.models import Q
from django.db.models.signals import post_migrate#, post_syncdb

post_t = (
    ('ad', u'管理员'),
    ('rm', u'审批经理'),
    ('rs', u'审批专员'),
    ('cm', u'催收经理'),
    ('cs_m1', u'催收专员M1'),
    ('cs_m2', u'催收专员M2'),
    ('cs_m3', u'催收专员M3'),
    ('cs_m4', u'催收专员M4'),
    ('cs_m5', u'催收专员M5'),
    ('cs_m5p', u'催收专员M5+'),
    ('op', u'运营经理'),
    ('o1', u'运营专员'),
    ('se', u'客服专员'),
    ('au', u'财务会计'),
    ('km', u'客户经理'),
    ('kp', u'客户专员'),
    ('other', u'其它职能')
)

# post_t = (
    # ('ad', u'管理员'),
    # ('an', u'数据分析师'),
    # ('rm', u'审批经理'),
    # # ('rz', u'审批主管'),
    # # ('r2', u'审批组长'),
    # ('rs', u'审批专员'),

    # ('cm', u'催收经理'),
    # ('cs', u'催收专员'),
    # ('op', u'运营经理'),
    # ('o1', u'运营专员'),
    # ('se', u'客服专员'),
    # ('au', u'财务会计'),
    # ('km', u'客户经理'),
    # ('kp', u'客户专员'),
# )



#class PermissionItem(models.Model):
#    url = models.CharField(max_length=255, help_text=u"路径")
#
#    class Meta:
#        db_table = 'permissionitem'
#
#    def ready(self):
#       post_migrate.connect(gen_default_permission, sender=self)
#
#    def __unicode__(self):
#        return u'%d): %s'%(self.id, self.url)

class Platform(models.Model):
    name = models.CharField(max_length = 64, primary_key = True)
    show_name = models.CharField(max_length = 64)
    description = models.CharField(max_length = 1024, blank = True, null = True)
    org_account = models.CharField(max_length = 64)
    account_prefix = models.CharField(max_length = 16, blank = True, null = True)

    class Meta:
        db_table = 'platform'

    def __unicode__(self):
        return u'%s %s' % (self.name, self.show_name)

class PermissionSet(models.Model):
    belong_system_name = models.CharField(max_length = 255, help_text = u'所属系统名')
    belong_sub_name = models.CharField(blank = True, null=True, max_length = 255, help_text = u'所属二级系统名')
    name = models.CharField(max_length = 255, help_text = u'权限集名称')
    #permissions = models.ManyToManyField(PermissionItem)
    permissions = models.CharField(max_length = 1024, help_text = u'url列表')

    class Meta:
        db_table = 'permissionset'

    def __unicode__(self):
        return u'%s' % self.name

class EmployeeGroup(models.Model):
    group_name = models.CharField(max_length = 255, help_text = u'用户组名')
    is_editable = models.IntegerField(help_text = u'是否允许编辑', blank = True, default = 1)
    permissions = models.ManyToManyField(PermissionSet)
    group_type = models.IntegerField(blank = True, default = 0)
    platform = models.CharField(max_length = 64)

    class Meta:
        db_table = 'employeegroup'

    def __unicode__(self):
        return u'%s %s' % (self.platform, self.group_name)

class Employee(models.Model):
    user = models.ForeignKey(User)
    username = models.CharField(max_length=255, help_text=u"员工姓名", default=u"待补充")
    mobile = models.CharField(blank=True, null=True, max_length=16)
    telephone = models.CharField(blank = True, null = True, max_length=32)
    #post字段是为了方便后台快速找出相应职能的员工，系统会对每个职能预设用户组
    post = models.CharField(blank = True, null = True, max_length = 16, choices = post_t)
    group_list = models.ManyToManyField(EmployeeGroup)
    leader = models.IntegerField(help_text = u'直属领导', default = 0)
    id_no = models.CharField(help_text = u'身份证号码', max_length = 32)
    platform_list = models.ManyToManyField(Platform)

    class Meta:
        db_table = 'employee'

    def __unicode__(self):
        return u'%d) %s'%(self.id, self.user.username)

    def check_page_permission(self, page):
        '''
            每个职位有权限访问的地址按照前缀匹配
        '''
        print page
        for group in self.group_list.all():
            for permission_set in group.permissions.all():
                for permission in permission_set.permissions.split(','):
                    if not permission.strip():
                        continue
                    if page.startswith(permission):
                        return True
        return False

    def get_permission_list(self):
        pm_set = set()
        for group in self.group_list.all():
            for permission_set in group.permissions.all():
                pm_set.add(permission_set)
                #for permission in permission_set.permissions:
                #    pm_set.add(permission.url)
        return list(pm_set)

    @classmethod
    def dive_collector(cls, collectors, collector_level, platform):
        level = {item['id']: item.get('coll_level', 'm1').upper() for item in collector_level}
        ret = {'M1': set(), 'M2': set(), 'M3': set(), 'M4': set(), 'M5': set(), 'M5+': set(), }
        m1_group = EmployeeGroup.objects.filter(group_name="催收M1", platform = platform).first()
        m2_group = EmployeeGroup.objects.filter(group_name="催收M2", platform = platform).first()
        m3_group = EmployeeGroup.objects.filter(group_name="催收M3", platform = platform).first()
        m4_group = EmployeeGroup.objects.filter(group_name="催收M4", platform = platform).first()
        m5_group = EmployeeGroup.objects.filter(group_name="催收M5", platform = platform).first()
        m5_group_above = EmployeeGroup.objects.filter(group_name="催收M5以上", platform = platform).first()
        for collector in collectors:
            if level.get(collector.id):
                ret[level[collector.id]].add(collector)
                continue
            group_list = collector.group_list.all()
            # group_ids = [item.id for item in group_list]
            groups = filter(lambda item: item in group_list, [m1_group, m2_group, m3_group, m4_group, m5_group, m5_group_above])
            if not groups:
                continue
            group = groups[0]
            ret[group.group_name[-2:]].add(collector)
        return ret

def create_employee(name, email, phone_no, chinese_name, post, group_list, platform):
    users = User.objects.filter(username = name)
    if len(users) == 0:
        user = User.objects.create_user(name, email, '123456')
        employee = Employee(user=user, username=chinese_name, mobile=phone_no, post = post)
    else:
        employees = Employee.objects.filter(user = users[0])
        if len(employees) != 0:
            #Log().info("create user:%s failed. user exist already"% name)
            return False
        employee = Employee(user=users[0], username=chinese_name, mobile=phone_no, post = post)
    employee.save()
    if group_list:
        for group in group_list:
            employee.group_list.add(group)
    platform_list = Platform.objects.filter(pk__in = platform.split(','))
    for p in platform_list:
        employee.platform_list.add(p)
    employee.save()
    #Log().info("create user:%s success"% name)
    return True


#@receiver(post_migrate)#, sender=EmplyeePermission)
#def gen_default_permission(sender, **kwargs):
#    '''
#        初始化权限列表
#    '''
#    p_set = PermissionSet(name = u'所有权限集合')
#    p_set.save()
#    p = PermissionItem(url = '/order')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/operation')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/admin')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/audit')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/new_order')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    group = EmployeeGroup(group_name = u'测试管理员', is_editable = 1)
#    group.save()
#    group.permissions.add(p_set)
#    group.save()
#
#    create_employee("admin", "admin@rst.com", "13928449141", u"管理员", 'other', [group])
#
#    p_set = PermissionSet(name = u'审批经理')
#    p_set.save()
#    p = PermissionItem(url = '/review/mine')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/all')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/info')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/action')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'审批专员')
#    p_set.save()
#    p = PermissionItem(url = '/review/mine')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/info')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/action')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'催收经理')
#    p_set.save()
#    p = PermissionItem(url = '/collection')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/user_view')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/query_detail')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/query')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/get_loan_data')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/get_collection_record_json')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/info/view')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/download_addressbook')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'催收专员')
#    p_set.save()
#    p = PermissionItem(url = '/collection/mine')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/info')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/action')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/my_collection_json')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/modal')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/get_collection_record_json')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/user_view')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/query')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/query_detail')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/get_loan_data')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/info/view')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/review/download_addressbook')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'运营经理')
#    p_set.save()
#    p = PermissionItem(url = '/operation')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/get_collection_record_json')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'运营专员')
#    p_set.save()
#    p = PermissionItem(url = '/operation')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/get_collection_record_json')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'客服')
#    p_set.save()
#    p = PermissionItem(url = '/custom')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/get_collection_record_json')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'财务会计')
#    p_set.save()
#    p = PermissionItem(url = '/audit')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/operation')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/user_view')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/query_detail')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/get_loan_data')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/custom/query')
#    p.save()
#    p_set.permissions.add(p)
#    p = PermissionItem(url = '/collection/get_collection_record_json')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'客户经理')
#    p_set.save()
#    p = PermissionItem(url = '/new_order')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()
#
#    p_set = PermissionSet(name = u'客户专员')
#    p_set.save()
#    p = PermissionItem(url = '/new_order')
#    p.save()
#    p_set.permissions.add(p)
#    p_set.save()

def check_employee(request):
    try:
        print request.user
        staff = Employee.objects.get(user = request.user)
        return staff.check_page_permission(request.path)
    except Exception, e:
        print 'check_employee failed, err:', e
        return False

def is_review_manager(request):
    try:
        staff = Employee.objects.get(user = request.user)
        #return staff.post == 'rm' or staff.post == "ad"
        return staff.post == "ad" or staff.post == "rz"
    except Exception, e:
        return False

def is_review_group_leader(request):
    try:
        staff = Employee.objects.get(user = request.user)
        return staff.post == 'r2'
    except Exception, e:
        return False

def get_collector_list():
    try:
        collectors = []
        employees = Employee.objects.filter()
        for employee in employees:
            if employee.user.username == 'admin':
                continue
            for g in employee.group_list.all():
                for p in g.permissions.all():
                    if p.name == u'逾期订单催收':
                        collectors.append(employee)
        return collectors
    except Exception, e:
        print e
        return []


def get_dispatch_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name__startswith="催收M")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def get_dispatch_M1_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name="催收M1")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def get_dispatch_M2_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name="催收M2")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def get_dispatch_M3_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name="催收M3")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def get_dispatch_M4_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name="催收M4")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def get_dispatch_M5_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name="催收M5")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def get_dispatch_above_M5_collector_list():
    try:
        res = []
        group = EmployeeGroup.objects.filter(group_name="催收M5以上")
        collectors = Employee.objects.filter(group_list__in=group)
        for c in collectors:
            if c.user.is_active == 1:
                res.append(c)
        return res
    except Exception, e:
        print e
        return []


def is_collection_manager(request):
    try:
        staff = Employee.objects.get(user = request.user)
        return staff.post == 'cm' or staff.post == 'ad'
    except Exception, e:
        return False

def get_employee(request):
    try:
        staff = Employee.objects.get(user = request.user)
        return staff
    except Exception, e:
        return None

def get_employee_platform(request):
    try:
        staff = Employee.objects.get(user = request.user)
        return staff.platform_list.all()
    except Exception, e:
        return None



def get_collector_employee_group():
    groups = EmployeeGroup.objects.filter(group_name__startswith="催收M")
    return groups
