# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import datetime

from django.core.cache import cache
from django.db import models
from business_manager.order.models import User
from business_manager.collection.models import RepaymentInfo
from business_manager.employee.models import Employee
from business_manager.config_center.models import WorkFlow

# 信息审核申请
from business_manager.util.wechat_notify_util import gen_key


class Apply(models.Model):

    WAITING = 'i0'
    WAIT_OUT_ING = 'i1'
    WAIT_OTHORS_ING = 'i2'
    WAIT_INTERVIEW_ING = 'i3'
    WAIT_MONEY = 's'
    WAIT_OUT = '1'
    WAIT_OTHORS = '2'
    WAIT_INTERVIEW = '3'
    WAIT = '0'
    WAIT_DATA = 'w'
    PROCESSING = 'i'
    COLLECTION = 'ci'
    PASS = 'y'
    BACK = 'r'
    REJECT = 'n'
    ASK_MONEY = 'p1'
    PAY_SUCCESS = 'p2'
    PAY_FAILED = 'p3'
    SEND_MIFAN_FAIL= 'p4'
    COLLECTION_SUCCESS = '8'
    # MECHINE_VERIFIED = 'a'
    # MECHINE_REJECT = 'b'
    REPAY_SUCCESS = '9'
    REPAY_FAILED = 'c'
    REPAY_ERROR= 'o'
    PARTIAL_SUCCESS = 'd'
    CANCELED = 'e'
    WAIT_CHECK = 'k'
    CHECK_FAILED = 't'

    # new status of collection.
    WAIT_DISTRIBUTION = 's1'
    NOT_ACCEPT = 's2'
    APPLY_PROCESSING = 's3'
    COMPLETED = 's4'

    # 续期
    RENEW = '10'

    # 失联
    LOST_CONTACT = 'lc'
    RECALL_SUCCESS = "rs"     # 召回成功
    RECALL_FAIL = "rf"       # 召回失败
    REPAIR_FAIL = 'rpf'      # 信修失败

    apply_status_t = (
        (WAIT_DISTRIBUTION, u'待分配'),
        (NOT_ACCEPT, u'未受理'),
        (APPLY_PROCESSING, u'已受理'),
        (COMPLETED, u'已完成'),

        (WAITING, u'正在初审'),
        (WAIT_OUT_ING, u'正在外访'),
        (WAIT_OTHORS_ING, u'正在三方'),
        (WAIT_INTERVIEW_ING, u'正在面签'),
        (WAIT_INTERVIEW, u'待面签'),
        (WAIT_OTHORS, u'待三方审核'),
        (WAIT_OUT, u'待外访'),
        (WAIT, u'待初审'),
        (WAIT_DATA, u'等待数据'),
        (PROCESSING, u'处理中'),
        (COLLECTION, u'已受理'),
        (PASS, u'通过'),
        (BACK, u'返回修改'),
        (REJECT, u'拒绝'),
        (WAIT_CHECK, u'待复核'),
        (CHECK_FAILED, u'复核失败'),

        (WAIT_MONEY, u'待放款'),
        (ASK_MONEY, u'请款中'),
        (PAY_SUCCESS, u'打款成功'),
        (PAY_FAILED, u'打款失败'),
        (SEND_MIFAN_FAIL, u'请求米饭放款失败'),
        (COLLECTION_SUCCESS, u'催收完成'),
        #(MECHINE_VERIFIED, u'机器审核'), # 额度提升中的自动审核
        #(MECHINE_REJECT, u'机器拒绝'), # 第一轮风控自动拒绝
        (REPAY_SUCCESS, u'扣款成功'),
        (REPAY_FAILED, u'扣款失败'),
        (PARTIAL_SUCCESS, u'部分成功'),
        (CANCELED, u'取消订单'), # 已注销用户
        (REPAY_ERROR, u'扣款异常'),

        (RENEW, u'续期'),

        (LOST_CONTACT, u'已失联'),
        (RECALL_SUCCESS, u'召回成功'),
        (RECALL_FAIL, u'召回失败'),
        (REPAIR_FAIL, u'信修失败'),
    )

    NONE_TYPE = 'n'

    PAY_LOAN = 'l'
    COLLECTION_M0 = 'a'
    COLLECTION_M1 = 'b'
    COLLECTION_M2 = 'c'
    COLLECTION_M3 = 'd'
    COLLECTION_M4 = 'e'
    COLLECTION_M5 = 'g'
    COLLECTION_M6 = 'h'

    REPAY_LOAN = 'p'
    BASIC = '0'
    WEIBO = '1'
    RENREN = '2'
    PHONE_CALL = '3'
    CREDIT = '4'
    BANK_FLOW = '5'
    OTHER = '6'
    EBUSINESS = '7'
    ALIPAY = '9'
    COMMODITY = 'f'
    SECOND_LOAN = 's'

    apply_type_t = (
        (NONE_TYPE, 'none'),
        (PAY_LOAN, u'提现'),

        (COLLECTION_M0, u'所有'),
        (COLLECTION_M1, u'催收m1'),
        (COLLECTION_M2, u'催收m2'),
        (COLLECTION_M3, u'催收m3'),
        (COLLECTION_M4, u'催收m4'),
        (COLLECTION_M5, u'催收m5'),
        (COLLECTION_M6, u'催收m5+'),

        (REPAY_LOAN, u'还款'),
        (BASIC, u'基本信息'),
        (WEIBO, u'微博'),
        (RENREN, u'人人'),
        (PHONE_CALL, u'通话记录'),
        (CREDIT, u'征信报告'),
        (BANK_FLOW, u'银行流水'),
        (OTHER, u'其他'),
        (EBUSINESS, u'淘宝/京东'),
        (ALIPAY, u'支付宝'),
        (COMMODITY, u'服务贷'),
        (SECOND_LOAN, u'二次提现'),
    )

    INFO_REPAIR = 'a'
    extra_choices = (
        (INFO_REPAIR, '信修'),
    )

    class Meta:
        db_table = u'apply'

    create_by = models.ForeignKey(User, related_name="apply_create_by_user")
    create_at = models.DateTimeField(auto_now_add=True, help_text = "创建时间")
    update_at = models.DateTimeField(auto_now_add=True, help_text = "更新时间, type, status 改变时.更新.")
    last_commit_at = models.DateTimeField(blank=True, null=True, auto_now_add=True, help_text = "最近提交时间") # 打回后重新提交/ 在催收apply中用来作为用户的承诺还款时间
    finish_time = models.DateTimeField(blank=True, null=True, help_text="完成时间")

    money = models.IntegerField(help_text="相关金额", default=0)

    status = models.CharField(default="0", max_length = 16, choices = apply_status_t, blank = True)
    type = models.CharField(default="n", max_length = 16, choices = apply_type_t, blank = True)

    # commodity_apply = models.ForeignKey('Commodityapply', blank=True, null=True)
    repayment = models.ForeignKey(RepaymentInfo, blank=True, null=True)

    pic = models.CharField(max_length = 64, help_text="相关图片", blank=True, null=True)
    experiment = models.CharField(max_length= 64, help_text="小流量测试", blank=True, null=True)


    platform = models.CharField(blank = True, null = True, max_length = 64)
    flow_id = models.IntegerField(blank=True, null=True)
    workflow = models.ForeignKey(WorkFlow, blank=True, null=True)
    product = models.CharField(max_length=64, blank=True)
    salesman = models.CharField(max_length=64, blank=True)
    strategy_id = models.IntegerField(blank=True, null=True)
    amount = models.IntegerField(blank=True, null=True)
    reason = models.CharField(max_length=512, blank=True)
    bill_address = models.CharField(max_length=512, blank=True)
    belong_group_id = models.IntegerField(blank=True, null=True, default=0)

    # 催收页面 使用, 每天会通过 定时脚本 进行更新
    # 期款: 未还款时为所有未还金额
    rest_repay_money = models.IntegerField(blank=True, null=True, default=0)
    # 已还金额
    real_repay_money = models.IntegerField(blank=True, null=True, default=0)
    # 委案金额, 逾期类型转变时, 更新
    ori_collection_amount = models.IntegerField(blank=True, null=True, default=0)

    overdue_days = models.IntegerField(blank=True, null=True)
    owner_type = models.IntegerField(blank=True, null=True ,help_text="转给审批人类型，0为个人，1为用户组")
    owner_id = models.CharField(max_length=1024, blank=True, null=True, help_text="审批人id")
    comment = models.CharField(max_length=1024, blank=True, null=True, help_text="评论")
    real_repay_time = models.DateTimeField(blank=True, null=True)
    collection_record_time = models.DateTimeField(blank=True, null=True)
    promised_repay_time = models.DateTimeField(blank=True, null=True)
    employee = models.ForeignKey(Employee, blank=True, null=True)

    should_repay_time = models.DateTimeField(blank=True, null=True)

    extra_info = models.CharField(max_length=64, blank=True, choices=extra_choices)

    def __unicode__(self):
        return u'%d)%s %s %s'%(self.id, self.create_by.name, self.get_type_display(), self.get_status_display())

    @classmethod
    def dive_orders(cls, orders):
        ret = OrderedDict()
        ret['M1'] = set()
        ret['M2'] = set()
        ret['M3'] = set()
        ret['M4'] = set()
        ret['M5'] = set()
        ret['M5+'] = set()
        for order in orders:
            if order.type == 'b':
                ret['M1'].add(order)
            elif order.type == 'c':
                ret['M2'].add(order)
            elif order.type == 'd':
                ret['M3'].add(order)
            elif order.type == 'e':
                ret['M4'].add(order)
            elif order.type == 'g':
                ret['M5'].add(order)
            elif order.type == 'h':
                ret['M5+'].add(order)
        return ret


# 催收运营提给财务复核的申请
# 不要问我为什么这个表拆开了，因为上面那一堆表本来就应该拆开，我是偷懒才把上面那些Apply才丢在了一张表里面
class CheckApply(models.Model):
    WAIT = '0'
    CHECK_SUCCESS = 'k'
    CHECK_FAILED = 't'

    apply_status_t = (
        (WAIT, u'等待复核'),
        (CHECK_SUCCESS, u'复核成功'),
        (CHECK_FAILED, u'复核失败'),
    )

    CHECK_ALIPAY = 'f'
    CHECK_TOPUBLIC = 'g'

    apply_type_t = (
        (CHECK_ALIPAY, u'支付宝转账'),
        (CHECK_TOPUBLIC, u'对公转账'),
    )

    REPAY_INSTALLMENT = 0
    REPAY_REPAYMENT = 0
    REPAY_CUSTOM = 0

    repay_type_t = (
        (REPAY_INSTALLMENT, u'期款'),
        (REPAY_REPAYMENT, u'全款'),
        (REPAY_CUSTOM, u'自定义'),
    )

    create_by = models.ForeignKey(Employee, related_name="apply_create_by_user")
    create_at = models.DateTimeField(auto_now_add=True, help_text = "创建时间")
    finish_time = models.DateTimeField(blank=True, null=True, help_text="完成时间")

    money = models.IntegerField(help_text="相关金额", default=0)

    status = models.CharField(default="0", max_length = 1, choices = apply_status_t)
    type = models.CharField(default="n", max_length = 1, choices = apply_type_t)
    notes = models.CharField(max_length = 255, help_text="备注", default="", null=True, blank=True)
    repayment = models.ForeignKey(RepaymentInfo, blank=True, null=True)
    repay_type = models.IntegerField(help_text="结清类型", default=0, choices = repay_type_t)
    installment = models.IntegerField(help_text="当前期数", default=0)
    repay_apply = models.ForeignKey(Apply, help_text="申请订单", blank=True, null=True)

    pic = models.CharField(max_length = 255, help_text="相关图片", blank=True, null=True)

    platform = models.CharField(max_length = 64, blank = True)
    product = models.CharField(max_length = 64, blank = True)

    class Meta:
        db_table = u'check_apply'

    def __unicode__(self):
        return u'%d)%s %s %s'%(self.id, self.create_by.username, self.get_type_display(), self.get_status_display())


class ExtraApply(models.Model):
    class Meta:
        db_table = u'extraapply'

    apply = models.OneToOneField(Apply, primary_key=True)
    review_label = models.CharField(max_length=63, default="", blank=True, null=True, help_text="审批标签")
    extra_pic = models.CharField(max_length=511, default="", blank=True, null=True, help_text="相关图片")
    message_1 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="打回信息1")
    message_2 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="打回信息2")
    message_3 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="打回信息3")
    message_4 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="打回信息4")
    message_5 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="打回信息5")
    message_6 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="打回信息6")
    message_7 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="外访报告")
    message_8 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="三方信息")
    message_9 = models.CharField(max_length=255, default="", blank=True, null=True, help_text="面签信息6")



    def __unicode__(self):
        return u')%s'%(self.apply.create_by.name)


class Commodity(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    name = models.CharField(max_length=255)
    desc = models.CharField(max_length=255)
    price = models.IntegerField()
    merchant = models.ForeignKey('Merchant', db_column='merchant', blank=True, null=True)
    create_at = models.DateTimeField()
    status = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'commodity'


# class Commodityapply(models.Model):
    # order_number = models.CharField(primary_key=True, max_length=255)
    # merchant = models.ForeignKey('Merchant', blank=True, null=True)
    # commodity = models.ForeignKey(Commodity)
    # status = models.IntegerField()
    # owner = models.ForeignKey('User')
    # create_at = models.DateTimeField()
    # strategy_id = models.IntegerField(blank=True, null=True)
    # salesman = models.ForeignKey('Salesman', blank=True, null=True)
    # down_payment = models.IntegerField(blank=True, null=True)

    # class Meta:
        # managed = False
        # db_table = 'commodityapply'

class Salesman(models.Model):
    code = models.CharField(primary_key=True, max_length=255)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    is_active = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'salesman'

class Merchant(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255)
    province = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    district = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    desc = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    salesman = models.ForeignKey('Salesman', db_column='salesman', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'merchant'


class InfoModule(models.Model):
    """
    信修模块
    """

    cn_name = models.CharField(max_length=512, default="", help_text=u"信修模块名")
    field_name = models.CharField(max_length=512, default="")

    class Meta:
        db_table = 'info_module'


class InfoField(models.Model):
    """
    信修字段
    """

    INVALID = 0
    VALID = 1
    NOT_VERIFY = 2

    STATUS_CHOICES = (
        (INVALID, u'无效'),
        (VALID, u'有效'),
        (NOT_VERIFY, u'未验证'),
    )

    cn_name = models.CharField(max_length=512, help_text=u"字段中文名")
    content = models.CharField(max_length=1024, default='', help_text=u"内容")
    status = models.IntegerField(choices=STATUS_CHOICES, default=NOT_VERIFY, help_text=u"状态")
    user = models.ForeignKey(User, help_text=u'对应用户')
    info_module = models.CharField(max_length=512, help_text=u'对应信修模块', default=u'默认')
    is_must = models.BooleanField(default=False, help_text=u'必验证字段')

    class Meta:
        db_table = 'info_field'


class RepairHistory(models.Model):
    """
    历史记录
    """

    info_field = models.ForeignKey(InfoField)
    operation_time = models.DateTimeField(auto_now_add=True, auto_now=True)
    employee = models.ForeignKey(Employee, help_text='操作人')
    operation_status = models.IntegerField(choices=InfoField.STATUS_CHOICES)

    class Meta:
        db_table = 'repair_history'
