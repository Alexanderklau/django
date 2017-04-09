# -*- coding: utf-8 -*-
'''
    借贷相关model 放在催收目录了。。
    RepaymentInfo : 用户的借贷信息
    InstallmentDetailInfo : 用户的每一期借贷详情
    BankRecord : 每一笔银行扣款/打款记录
'''
from datetime import datetime, date
from xlrd import xldate_as_tuple
from django.db import models

from business_manager.order.models import User, BankCard
from business_manager.strategy.models import Strategy2

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.employee.models import Employee

class RepaymentInfo(models.Model):
    REJECT = -3
    DELETED = -2
    TO_BE_COMFIRMED = -1
    PAYING = 0
    REPAYING = 1
    OVERDUE = 2
    DONE = 3
    CHECKING = 4
    PAYED =5
    PASS = 6
    PRE_DONE = 7
    OVERDUE_DONE = 8
    RENEW = 10

    repay_status_type_t = (
        (-3, '拒绝'),
        (-2, '已删除'),
        (-1, '合同待确认'),
        (0, '放款中'),
        (1, '还款中'),
        (2, '逾期'),
        (3, '已完成'),
        (4, '审核中'),
        (5, '已放款'),
        (6, '审核通过'),
        #----后面两个状态仅供InstallmentDetailInfo.repay_status使用
        (7, '---'),
        (8, '逾期完成'),
        (9, '提前还款'),
        (10, '续期'),
    )

    strategy_type_t = (
        (1, u'28天一次性'),
        (2, u'21天一次性'),
        (3, u'14天一次性'),
        (4, u'7天一次性'),
        (5, u'28天分期'),
        (6, u'21天分期'),
        (7, u'14天分期'),
        (10, u'21天'),
        (11, u'28天'),
        (12, u'三个月'),
        (13, u'六个月'),
        (14, u'十二个月'),
        (15, u'学生三个月'),
        (19, u'12个月'),
        (20, u'24个月'),
        (21, u'36个月'),
    )

    XINTUO = 1
    MIFAN = 2
    JIUFU = 3
    capital_type_t = (
        (XINTUO, u'信托'),
        (MIFAN, u'米饭'),
        (JIUFU, u'玖富'),
    )

    class Meta:
        db_table = u'repaymentinfo'

    def __unicode__(self):
        return u'%d)%s %d %s'%(self.id, self.user.name, self.apply_amount/100, self.get_repay_status_display())

    order_number = models.CharField(max_length=255, help_text='订单号') #订单号，全局唯一
    repay_status = models.IntegerField(choices=repay_status_type_t, help_text='还款状态')
    apply_amount = models.IntegerField(default=0, help_text='申请金额')
    exact_amount = models.IntegerField(default=0, help_text='实际打款金额')
    repay_amount = models.IntegerField(default=0, help_text='需还金额')
    rest_amount = models.IntegerField(default=0, help_text='剩余未还金额')
    user = models.ForeignKey(User, help_text='贷款人')
    # strategy_id = models.IntegerField(choices=strategy_type_t, help_text='策略id')
    strategy = models.ForeignKey(Strategy2, help_text='策略', blank=True, null=True)
    capital_channel_id = models.IntegerField(choices=capital_type_t, help_text='资金渠道', default=MIFAN, blank = True)

    bank_card = models.ForeignKey(BankCard, help_text='此次交易所属的银行卡', null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True, null=True, help_text='用途')
    apply_time = models.DateTimeField(auto_now_add=True, help_text='申请时间')
    first_repay_day = models.DateTimeField(blank=True, null=True, help_text='打款日 (计息日)')
    next_repay_time = models.DateTimeField(blank=True, null=True, help_text='下次还款日')
    last_time_repay = models.DateTimeField(blank=True, null=True, help_text='最后一次还款日期')

    score = models.IntegerField(default=0, help_text='使用积分', blank = True)
    overdue_days = models.IntegerField(default=0, help_text='当前逾期天数', blank = True)
    overdue_days_total = models.IntegerField(default=0, help_text='总逾期天数', blank = True)

    platform = models.CharField(max_length = 64, blank = True)
    product = models.CharField(max_length = 64, blank = True)

    # import_id = models.IntegerField(default=0, help_text='外部导入的id')

    # rest_amount = models.IntegerField(default=0, blank = True)

    rest_principle = models.IntegerField(default=0, blank = True)
    balance = models.IntegerField(default=0, blank = True)
    last_calc_overdue_time = models.DateTimeField(blank=True, null=True)

    installment_count = models.IntegerField(default=0, help_text='总共多少期')
    def get_repayments_days(self):
        if self.strategy_id == 1 or self.strategy_id == 5:
            return 28
        elif self.strategy_id == 2 or self.strategy_id == 6:
            return 21
        elif self.strategy_id == 3 or self.strategy_id == 7:
            return 14
        elif self.strategy_id == 4:
            return 7
        else:
            return -1

    def get_repayments_instalments(self):
        if self.strategy_id >= 1 and self.strategy_id <= 4:
            return 1
        elif self.strategy_id == 5:
            return 4
        elif self.strategy_id == 6:
            return 3
        elif self.strategy_id == 7:
            return 2
        else:
            return -1

    def get_strategy_rate(self):
        if self.strategy_id >= 1 and self.strategy_id <= 4:
            return 0.27
        elif self.strategy_id >= 5 and self.strategy_id <= 7:
            return 0.24
        else:
            return -1


    def get_first_installments_amount(self):
        total = self.apply_amount
        return total - total / self.get_repayments_instalments() * (self.get_repayments_instalments() - 1)


class InstallmentDetailInfo(models.Model):

    repay_status_type_t = (
        (-3, u'拒绝'),
        (-2, u'已删除'),
        (-1, u'合同待确认'),
        (0, u'放款中'),
        (1, u'还款中'),
        (2, u'逾期'),
        (3, u'已完成'),
        (4, u'审核中'),
        (5, u'已放款'),
        (6, u'审核通过'),
        #---u-后面两个状态仅供InstallmentDetailInfo.repay_status使用
        (7, u'---'),
        (8, u'逾期完成'),
        (9, u'提前还款'),
        (10, u'续期'),
    )

    REPAY_TYPE_AUTO = 1
    REPAY_TYPE_ALIPAY = 3
    REPAY_TYPE_PUB = 4
    repay_channel_type_t = (
        (0, u'---'),
        (1, u'自动扣款'),
        (2, u'手动扣款'),
        (3, u'支付宝'),
        (4, u'对公还款'),
        (5, u'其他'),
    )

    repay_app_type_t = (
        (1, u'按时还款'),
        (2, u'催收m1'),
        (3, u'催收m2'),
        (4, u'催收m3'),
        (5, u'催收m4'),
        (6, u'催收m5'),
        (7, u'催收m5+')
    )

    class Meta:
        db_table = u'installmentdetailinfo'

    def __unicode__(self):
        #return u'%s)%d-%d '%(self.repayment.user.name, self.repayment, self.installment_number)
        return u'%d)%s: %d-%d '%(self.id, self.repayment.user.name, self.repayment.id, self.installment_number)

    repayment = models.ForeignKey(RepaymentInfo)                                   #所属的交易
    installment_number = models.IntegerField()                                     #第几期
    order_number = models.CharField(max_length=255, help_text='订单号', blank = True, null = True)            #订单号，全局唯一
    should_repay_time = models.DateTimeField()                                     #应还日期
    real_repay_time = models.DateTimeField(blank=True, null=True)                  #实际还款日期
    should_repay_amount = models.IntegerField(help_text="期款")                    #期款 #应还金额(当前 用户看) = 本金 + 利息 + 服务费 + 银行手续费
    repay_overdue = models.IntegerField(default=0, help_text="罚金")               #罚金 # 应还罚款 = 罚息 + 罚金
    real_repay_amount = models.IntegerField(default=0, help_text="实际还款金额")   #实际还款金额
    reduction_amount = models.IntegerField(default=0, help_text="减免金额")        #减免金额

    repay_status = models.IntegerField(choices=repay_status_type_t)       #归还状态
    repay_channel = models.IntegerField(choices=repay_channel_type_t, default=0)     #还款途径，比如1表示自助扣款，2表示XX方式还款
    repay_channel_description = models.CharField(max_length=255, default='')                         #还款途径描述: repay_channel = 其他 类型时使用

    repay_overdue = models.IntegerField(default=0) # 应还罚款 = 罚息 + 罚金
    repay_principle = models.IntegerField(default=0)  #应还本金
    repay_overdue_interest = models.IntegerField(blank = True, default=0)   # 应还罚息
    repay_penalty = models.IntegerField(blank = True, default=0) # 应还罚金
    repay_bank_fee = models.IntegerField(default=0) #应还手续费 (银联)
    repay_interest = models.IntegerField(default=0)#应还利息
    repay_fee = models.IntegerField(default=0)#应还服务费
    overdue_days = models.IntegerField(default=0, blank = True)       # 当前逾期天数

    ori_should_repay_amount = models.IntegerField(help_text="委案金额")
    real_time_should_repay_amount = models.IntegerField(help_text="应还金额(总)", default=0) #应还金额(总) >= should_repay_amount +  repay_overdue
    update_at = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)


class BankRecord(models.Model):
    class Meta:
        db_table = u'bankrecord'
    amount = models.IntegerField(int)                         #扣款金额
    banck_code = models.CharField(max_length=20)              #银行卡号
    status = models.IntegerField()                            #扣款状态
    create_at = models.DateTimeField(auto_now_add=True)       #扣款时间
    related_record = models.ForeignKey(InstallmentDetailInfo) #对应分期记录


class Repayrecord(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    exact_amount = models.IntegerField()
    exact_principle = models.IntegerField()
    exact_interest = models.IntegerField()
    exact_fee = models.IntegerField()
    exact_overdue_interest = models.IntegerField()
    exact_penalty = models.IntegerField()
    exact_bank_fee = models.IntegerField()
    bank_card = models.ForeignKey(BankCard, blank=True, null=True)
    status = models.IntegerField()
    create_at = models.DateTimeField()
    repay_channel = models.IntegerField()
    repayment = models.ForeignKey(RepaymentInfo)

    class Meta:
        managed = False
        db_table = 'repayrecord'


class Repayinstallmentrecord(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    repay_record = models.ForeignKey('Repayrecord')
    exact_amount = models.IntegerField()
    exact_principle = models.IntegerField()
    exact_interest = models.IntegerField()
    exact_fee = models.IntegerField()
    exact_overdue_interest = models.IntegerField()
    exact_penalty = models.IntegerField()
    exact_bank_fee = models.IntegerField()
    bank_card = models.ForeignKey(BankCard, blank=True, null=True)
    status = models.IntegerField()
    create_at = models.DateTimeField()
    repay_channel = models.IntegerField()
    repayment = models.ForeignKey('Repaymentinfo')
    installment = models.ForeignKey(InstallmentDetailInfo)

    class Meta:
        managed = False
        db_table = 'repayinstallmentrecord'


class InstallmentRecord(models.Model):
    """期款的快照"""

    class Meta:
        db_table = u'installment_record'

    def __unicode__(self):
        #return u'%s)%d-%d '%(self.repayment.user.name, self.repayment, self.installment_number)
        return u'%d)%s: %d-%d '%(self.id, self.repayment.user.name, self.repayment.id, self.installment_number)

    repayment = models.ForeignKey(RepaymentInfo)                                   #所属的交易
    installment_number = models.IntegerField()                                     #第几期
    order_number = models.CharField(max_length=255, help_text='订单号', blank = True, null = True)            #订单号，全局唯一
    should_repay_time = models.DateTimeField()                                     #应还日期
    real_repay_time = models.DateTimeField(blank=True, null=True)                  #实际还款日期
    should_repay_amount = models.IntegerField(help_text="期款")                    #期款 #应还金额(当前 用户看) = 本金 + 利息 + 服务费 + 银行手续费
    repay_overdue = models.IntegerField(default=0, help_text="罚金")               #罚金 # 应还罚款 = 罚息 + 罚金
    real_repay_amount = models.IntegerField(default=0, help_text="实际还款金额")   #实际还款金额
    reduction_amount = models.IntegerField(default=0, help_text="减免金额")        #减免金额

    repay_status = models.IntegerField()       #归还状态
    repay_channel = models.IntegerField(default=0)     #还款途径，比如1表示自助扣款，2表示XX方式还款
    repay_channel_description = models.CharField(max_length=255, default='')                         #还款途径描述: repay_channel = 其他 类型时使用

    repay_overdue = models.IntegerField(default=0) # 应还罚款 = 罚息 + 罚金
    repay_principle = models.IntegerField(default=0)  #应还本金
    repay_overdue_interest = models.IntegerField(blank = True, default=0)   # 应还罚息
    repay_penalty = models.IntegerField(blank = True, default=0) # 应还罚金
    repay_bank_fee = models.IntegerField(default=0) #应还手续费 (银联)
    repay_interest = models.IntegerField(default=0)#应还利息
    repay_fee = models.IntegerField(default=0)#应还服务费
    overdue_days = models.IntegerField(default=0, blank = True)       # 当前逾期天数

    renew_time = models.DateTimeField(help_text='续期时间')
    strategy = models.ForeignKey(Strategy2, help_text='策略', blank=True, null=True)

    ori_should_repay_amount = models.IntegerField(help_text="委案金额")
    real_time_should_repay_amount = models.IntegerField(help_text="应还金额(总)", default=0) #应还金额(总) >= should_repay_amount +  repay_overdue
    update_at = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)


class InspectionDetails(models.Model):
    """
    质检详情
    """

    normal = u'正常'
    warn = u'警告'
    lost_work = u'作业疏失'
    offline = u'下线学习'

    normal_code = 0
    warn_code = 1
    lost_code = 2
    offline_code = 3

    level_choice = (
        (normal_code, normal),
        (warn_code, warn),
        (lost_code, lost_work),
        (offline_code, offline),
    )

    trigger_level = (
        (1, u'普通'),
        (2, u'首次警告，再次作业疏失'),
        (3, u'首次作业疏失，再次下线学习'),
    )

    cn_name = models.CharField(max_length=500, verbose_name=u'质检详情')
    warn_level = models.IntegerField(choices=level_choice, verbose_name=u'处理', default=0)
    trigger_level = models.IntegerField(choices=trigger_level, default=1)

    class Meta:
        db_table = 'inspection_details'

    @classmethod
    def get_detail(cls, cn_name, treatment):
        instance = cls.objects.filter(cn_name=cn_name.strip()).first()
        if not instance:
            if treatment == cls.warn:
                level = cls.warn_code
            elif treatment == cls.lost_work:
                level = cls.lost_code
            elif treatment == cls.offline:
                level = cls.offline_code
            else:
                level = cls.normal_code
            instance = cls.objects.create(cn_name=cn_name, warn_level=level)
        return instance


class QualityControlRecord(models.Model):

    normal = 1
    deleted = -1
    record_status = (
        (normal, u"正常"),
        (deleted, u"删除")
    )

    cn_group = models.CharField(max_length=100, verbose_name=u'组名')
    employee = models.ForeignKey(Employee, related_name='collector',
                                 verbose_name=u'催收员')
    order_number = models.CharField(max_length=50, verbose_name=u'客户工单号')
    customer = models.CharField(max_length=100, verbose_name=u'客户姓名')
    customer_phone = models.CharField(max_length=50, verbose_name=u'客户电话')
    recording_time = models.DateTimeField(null=True, verbose_name=u'录音时间')
    inspection_detail = models.ForeignKey(InspectionDetails,
                                          verbose_name=u'质检详情')
    quality_people = models.ForeignKey(Employee, related_name='quality_people',
                                       verbose_name=u'质检人')
    create_at = models.DateTimeField(auto_now_add=True)
    treatment = models.CharField(max_length=100, verbose_name=u'处理', null=True, blank=True)
    check_time = models.DateTimeField(verbose_name='质检时间')

    status = models.IntegerField(default=1, choices=record_status)

    class Meta:
        db_table = 'quality_control_record'

    @classmethod
    def import_record(cls, date_, data):
        success = 0
        fail = 0
        ret_list = []
        for line in data:
            try:
                print "befor import: ",  line
                if isinstance(line['recording_time'], (int, float)):
                    line['recording_time'] = datetime(*xldate_as_tuple(line['recording_time'], 0))
                elif isinstance(line['recording_time'], (unicode, str)):
                    if "/" in line['recording_time']:
                        line['recording_time'] = line['recording_time'].replace("/", "-")
                if not line['treatment']:
                    line['treatment'] = ''
                line['employee'] = Employee.objects.filter(username=line['employee']).first()
                line['quality_people'] = Employee.objects.filter(username=line['quality_people']).first()
                line['inspection_detail'] = InspectionDetails.get_detail(line['inspection_detail'], line['treatment'])
                trigger_level = line['inspection_detail'].trigger_level
                records = cls.objects.filter(
                    inspection_detail=line['inspection_detail'],
                    check_time__month=date_.month)
                if records:
                    if trigger_level == 2:
                        line['treatment'] = InspectionDetails.lost_work
                    elif trigger_level == 3:
                        line['treatment'] = InspectionDetails.offline
                line['check_time'] = date_
                print "import record: ",  line
                ret = QualityControlRecord.objects.create(**line)
                ret_list.append(ret)
            except Exception as e:
                print('QualityControlRecord import_record error: ', e)
                fail += 1
                print "\nret_list", ret_list
                for item in ret_list:
                    item.delete()
                return {'success': 0, 'fail': len(data)}
            success += 1
        return {'success': success, 'fail': fail}

