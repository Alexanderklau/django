#!/usr/bin/env python
# coding=utf-8

from django.db import models
#from business_manager.employee.models import Platform
from business_manager.order.models import User

class LocationConf(models.Model):
    """"""
    platform = models.CharField(max_length=64, blank=True)
    is_on = models.IntegerField(default=0)
    frequency = models.TextField()

    class Meta:
        db_table = 'locationconf'


class Location(models.Model):
    """"""
    user = models.ForeignKey(User, db_column='user')
    longitude = models.CharField(max_length=255)
    latitude = models.CharField(max_length=255)
    description = models.CharField(max_length=256)
    collected_time = models.DateTimeField(auto_now_add=True)
    appeared_count = models.IntegerField()
    province = models.CharField(max_length=24)
    city = models.CharField(max_length=24)

    class Meta:
        db_table = 'location'


class ProfileField(models.Model):
    name = models.CharField(max_length = 64, blank = True, help_text='变量对应的名字')
    show_name = models.CharField(max_length = 64, blank = True, help_text='字段展示的中文名称')
    description = models.CharField(max_length = 128, help_text='字段描述', blank = True)
    type = models.CharField(max_length = 64, help_text='字段类型')
    reserve = models.CharField(max_length = 2048, blank = True, help_text='预留字段')
    is_inner = models.IntegerField(default = 0, max_length = 1, blank = True, help_text='是否为预置字段，0否，1是')
    is_in_use = models.IntegerField(default = 0, help_text = '是否上线使用，0未使用，1使用中')
    is_delete = models.IntegerField(default = 0, help_text = '是否被删除，0未被删除，1已删除')
    use_times = models.IntegerField(default = 0, help_text = '被使用次数')
    platform = models.CharField(max_length = 64)

    class Meta:
        db_table = 'profilefield'

    def __unicode__(self):
        return u'%d): %s' % (self.id, self.show_name)

class ProfileModule(models.Model):
    show_name = models.CharField(max_length = 32, blank = True, help_text='模块展示的中文名称')
    description = models.CharField(max_length = 128, help_text='模块描述', blank = True)
    #layout以前定义的，先留着吧
    layout = models.CharField(max_length = 64, blank = True, help_text = '排版方式')
    required_fields = models.CharField(max_length = 5120, help_text = '必填字段')
    optional_fields = models.CharField(max_length = 256, blank = True, help_text = '选填字段')
    is_inner = models.IntegerField(default = 0, max_length = 1, blank = True, help_text='是否为预置模块，0否，1是')
    is_in_use = models.IntegerField(default = 0, help_text = '是否上线使用，0未使用，1使用中')
    is_delete = models.IntegerField(default = 0, help_text = '是否被删除，0未被删除，1已删除')
    use_times = models.IntegerField(default = 0, help_text = '被使用次数')
    platform = models.CharField(max_length = 64)

    class Meta:
        db_table = 'profilemodule'

    def __unicode__(self):
        return u'%d): %s' % (self.id, self.show_name)

class ProfileFlow(models.Model):
    show_name = models.CharField(max_length = 64, blank = True, help_text='模板展示的中文名称')
    description = models.CharField(blank=True, null=True, max_length = 128, help_text = '流程描述')
    required_modules = models.CharField(max_length = 1024, help_text = '包含的模块，json格式')
    belong_product = models.CharField(blank=True, null=True, max_length = 64, help_text = '流程属于哪个产品')
    belong_system = models.CharField(default= "进件子系统", max_length = 64, help_text = '流程属于哪个子系统')
    is_in_use = models.IntegerField(default = 0, help_text = '是否上线使用，0未使用，1使用中')
    is_delete = models.IntegerField(default = 0, help_text = '是否被删除，0未被删除，1已删除')
    use_times = models.IntegerField(default = 0, help_text = '被使用次数')
    platform = models.CharField(max_length = 64)

    class Meta:
        db_table = 'profileflow'

    def __unicode__(self):
        return u'%d): %s' % (self.id, self.show_name)

class ExperimentPercentage(models.Model):
    percentage = models.IntegerField(default = 0, help_text = '百分比')
    experiment_name = models.CharField(max_length = 128, help_text = '实验描述')
    create_time = models.DateTimeField(auto_now_add=True, help_text = "创建时间")
    is_in_use = models.IntegerField(default = 0, help_text = '是否上线使用')

    class Meta:
        db_table = 'experimentpercentage'

class ReviewExperiment(models.Model):
    filter = models.CharField(max_length = 512, help_text = '满足此规则的用户使用此模型，json格式')
    model_id = models.CharField(max_length = 64, help_text = '模型名')
    belong = models.ForeignKey(ExperimentPercentage)

    class Meta:
        db_table = 'reviewexperiment'


class WorkFlow(models.Model):
    name = models.CharField(max_length = 64, blank = True, help_text = "工作流名称")
    description = models.CharField(max_length = 256, help_text='工作流描述', blank = True)
    belong = models.CharField(default="review", max_length = 10, blank = True, help_text = "所属子系统")
    is_in_use = models.IntegerField(default = 0, help_text = '是否上线使用')
    is_delete = models.IntegerField(default = 0, help_text = '是否被删除，0未被删除，1已删除')
    is_used = models.IntegerField(default = 0, help_text = '该工作流是否被使用过，0未被使用过，1使用过')
    platform = models.CharField(max_length = 64)
    belong_product = models.CharField(blank = True, null = True, max_length = 64)

    def __unicode__(self):
        return u'%d): %s - %s' % (self.id, self.name, self.description)

    class Meta:
        db_table = 'workflow'

class WorkStatus(models.Model):
    name = models.CharField(max_length = 64, blank = True, help_text = "状态名称")
    other_name = models.CharField(max_length = 64, blank = True, help_text = "状态别名")
    description = models.CharField(max_length = 256, help_text='状态描述',blank=True, null=True)
    status_code = models.CharField(max_length = 2, help_text='状态码')
    is_delete = models.IntegerField(default = 0, help_text = '是否被删除，0未被删除，1已删除')
    is_start = models.IntegerField(default = 0, help_text = '是否为起始状态，0不是，1是')
    is_end = models.IntegerField(default = 0, help_text = '是否为结束态，0不是，1是')
    is_inner = models.IntegerField(default = 0, help_text = '是否为预置状态，0不是，1是')
    workflow = models.ForeignKey(WorkFlow, blank=True, null=True )
    platform = models.CharField(max_length = 64)
    
    # permission_scale = models.IntegerField(blank=True, null=True, help_text = '状态权限，用户个人还是用户组，0个人，1用户组，空为全部用户')
    # permission_obj_id = models.IntegerField(blank=True, null=True,help_text = '权限对象id(Employee)')

    def __unicode__(self):
        return u'%d): %s - %s' % (self.id, self.name, self.other_name)

    class Meta:
        db_table = 'workstatus'


class StatusFlow(models.Model):
    flow_id = models.IntegerField(help_text = '工作流id')
    status_id = models.IntegerField(help_text = '状态id')
    next_status_id = models.IntegerField(help_text = '下一状态id')
    template_id = models.CharField(max_length=256, blank=True, null=True,help_text = '该状态需要填写资料模板id')

    def __unicode__(self):
        return u'%d): %d - %d - %d' % (self.id, self.flow_id, self.status_id, self.next_status_id)

    class Meta:
        db_table = 'statusflow'

class Product(models.Model):
    name = models.CharField(max_length = 64)
    show_name = models.CharField(max_length = 64, help_text = '展示的产品名')
    description = models.CharField(max_length = 256, blank = True, null = True)
    service_id = models.CharField(max_length = 128, blank = True, null = True)
    platform = models.CharField(max_length = 64, blank = True) 
    is_in_use = models.IntegerField(default = 0, help_text = '是否启用')

    def __unicode__(self):
        return u'%d): %s %s' % (self.id, self.platform, self.show_name)

    class Meta:
        db_table = 'product'

