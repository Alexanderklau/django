# -*- coding:utf-8 -*-
from django.db import models

from business_manager.employee.models import Employee
from business_manager.import_data.models import status_choices


class Strategy2(models.Model):
    installment_type_choices = (
        (1, u'月利率'),
        (2, u'日利率'),
    )
    repay_time_type_choices = (
        (1, u'对日还款'),
        (2, u'指定日还款'),
    )
    type_choices = (
        (1, u'等额本息'),
        (2, u'等额本金'),
        (3, u'按日利率计息'),
        (4, u'简易等额本息'),
    )

    strategy_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    pre_factorage = models.FloatField(default=0)         # 前置手续费率
    post_factorage = models.FloatField(default=0)        # 后置手续费率
    interest = models.FloatField()              # 月利率/日利率(后置)
    installment_count = models.IntegerField()   # 分期 期数
    installment_days = models.IntegerField()    # 一期的天数/月数
    installment_type = models.IntegerField(choices=installment_type_choices)    # 利率类型
    amount_ceil = models.IntegerField(blank=True, null=True)    # 贷款金额 上限
    amount_floor = models.IntegerField(blank=True, null=True)   # 贷款金额 下限
    repay_time_type = models.IntegerField(choices=repay_time_type_choices)  # 贷款金额 下限
    repay_time_ori_day = models.DateTimeField(blank=True, null=True)    # 还款时间: datetime, 只用作展示.
    repay_time_day = models.IntegerField(blank=True, null=True)         # 指定日还款: 账单计算日
    repay_time_offset = models.IntegerField(blank=True, null=True)      # 指定日还款: 账单计算时间 + 延迟天数 = 还款时间
    repay_time_description = models.CharField(max_length=255, blank=True, null=True)    # 还款时间的备注
    type = models.IntegerField(choices=type_choices)                # 贷款算法类型
    using_count = models.IntegerField(default=0)                    # 贷款次数: 有多少笔贷款使用了该策略
    creator = models.ForeignKey(Employee, null=True, help_text='创建者')


    overdue_factorage = models.IntegerField(default=0)            # 逾期手续费
    overdue_interest = models.FloatField(default=0)      # 逾期m1利率 (日)
    overdue_m2_interest = models.FloatField(default=0)   # 逾期m2利率 (日)
    overdue_m3_interest = models.FloatField(default=0)   # 逾期m3利率
    m1_days = models.IntegerField(default=30)   # m1计算时间
    m2_days = models.IntegerField(default=60)   # m2计算时间
    m3_days = models.IntegerField(default=90)   # m3计算时间
    discount = models.FloatField(default=100)   # 折扣, 百分比 (历史残留 看起来暂时没用了),
    description = models.CharField(max_length=255, default='')              # 描述文字 (返回前端展示)
    strategy_description = models.CharField(max_length=255, default='')     # 策略描述文字 (返回前端展示)
    active = models.IntegerField(default=0)     # 是否使用 -- 弃用

    # 旧字段, 不知道有没有用
    belong_platform = models.CharField(max_length=255, blank=True, null=True, default='')
    belong_product = models.CharField(max_length=255, blank=True, null=True, default='')

    # platform = models.CharField(max_length = 64, blank = True)
    # product = models.CharField(max_length = 64, blank = True)

    status = models.IntegerField(default=0, choices=status_choices)
    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now_add=True)


    def __unicode__(self):
        return u'{}) {} {}'.format(self.strategy_id, self.name, self.installment_count)

    class Meta:
        managed = False
        db_table = 'strategy2'


class ExtraInterest(models.Model):
    """额外的利率
    """
    # 额外利率: 每期金额计算时, 需要加上
    # 月利率下级: 多条数据相加 = 月利率. 只是展示.
    type_choices = (
        (1, u'额外利率'),
        (2, u'月利率下级'),
    )
    # 元, 百分比 都只保留 2位小数, 所以 *100.
    value_type_choices = (
        (1, u'分'),
        (2, u'百分比'),
    )
    name = models.CharField(max_length=255)                         # 利率名称
    type = models.IntegerField(choices=type_choices)                # 利率类型
    value = models.FloatField()                                     # 利率值
    value_type = models.IntegerField(choices=value_type_choices)    # 数据类型
    installment_number = models.IntegerField(default=0)             # 对应期数, 0 表示全部

    strategy = models.ForeignKey(Strategy2)

    platform = models.CharField(max_length = 64, blank = True)
    product = models.CharField(max_length = 64, blank = True)

    status = models.IntegerField(default=0, choices=status_choices)
    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u'{}) {} {}'.format(self.strategy_id, self.name, self.type)

    class Meta:
        managed = False
        db_table = 'extrainterest'



