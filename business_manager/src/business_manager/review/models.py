# -*- coding: utf-8 -*-
from django.db import models

from business_manager.order.apply_models import Apply, ExtraApply, CheckApply
from business_manager.employee.models import Employee
from business_manager.order.models import BankCard, User, Messagetemplate
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo
from business_manager.python_common.log_client import CommonLog as Log

from business_manager.import_data.models import status_choices

from django.dispatch import receiver
from django.db.models.signals import post_migrate, post_syncdb

import datetime

review_status_t = (
    ('s', u'待放款'),
    ('3', u'待面签'),
    ('2', u'待三方审核'),
    ('1', u'待外访'),
    ('w', u'等待审批'),
    ('i', u'审批中'),
    ('r', u'打回修改'),
    ('y', u'通过 '),
    ('n', u'拒绝 '),
    ('s1', u'审批状态1'),
    ('s2', u'审批状态2'),
    ('s3', u'审批状态3'),
    ('s4', u'审批状态4'),
    ('s5', u'审批状态5'),
    ('s6', u'审批状态6'),
    ('s7', u'审批状态7'),
    ('s8', u'审批状态8'),
    ('s9', u'审批状态9'),
)

REVIEW_STATUS_PASS = 0xff

class Review(models.Model):
    order = models.ForeignKey(Apply, help_text="审批订单")
    reviewer = models.ForeignKey(Employee, related_name="reviewer", help_text="当前审批人员")
    reviewer_done = models.ForeignKey(Employee, related_name="reviewer_done", help_text="完成审批人员", blank=True, null=True) #废弃了 一个reviewer对应一个review
    create_at = models.DateTimeField()
    finish_time = models.DateTimeField(blank=True, null=True)

    review_res = models.CharField(max_length=2, help_text="审批结果", default="n", choices=review_status_t)
    money = models.IntegerField(help_text="相关金额", default=0)

    labels = models.ManyToManyField('Label', help_text="审批标签")
    status = models.IntegerField(default=0)

    def __unicode__(self):
        return u'%s)%s - %s'%(self.reviewer.username ,self.order.create_by.name, self.order.id)

    def status_to_int(self, status):
        if status == 'y' : #通过
            return 3
        elif status == 'n' : #拒绝
            return 2
        elif status == 'r' : #打回修改
            return 0
        elif status == 'i' : #审批中
            return 1
        else:
            return -1

    def set_label_list(self, label_list, apply):
        if len(label_list) == 0:
            return
        labels = label_list.split(",")
        for label in labels:
            #print label
            l = Label.objects.get(label_id = label)
            if l.label_id == 402: #无借款用途
                extra_apply = ExtraApply.objects.filter(apply=apply)
                if len(extra_apply) == 0:
                    extra_apply = ExtraApply()
                    extra_apply.apply = apply
                else:
                    extra_apply = extra_apply[0]
                extra_apply.review_label = "usage"
                extra_apply.save()
            self.labels.add(l)
        self.save()

    def get_label_list(self):
        return self.labels

    # 两位一个状态，从低到高依次是个人基本信息（姓名、身份证号码）、联系人信息、学信网、身份证照片
    def to_apply_status(self):
        try:
            status = 0
            records = ReviewRecord.objects.filter(review = self, review_type = 'i').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 0

            records = ReviewRecord.objects.filter(review = self, review_type = 'f').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 2

            records = ReviewRecord.objects.filter(review = self, review_type = 'c').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 4

            records = ReviewRecord.objects.filter(review = self, review_type = 'p').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 6

            records = ReviewRecord.objects.filter(review = self, review_type = 'o').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 8

            records = ReviewRecord.objects.filter(review = self, review_type = 'q').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 10

            #通话记录暂时全部通过
            status |=  0x3 << 12

            records = ReviewRecord.objects.filter(review = self, review_type = 'w').order_by("-id")
            if len(records) <= 0:
                return -1
            status |= self.status_to_int(records[0].review_status) << 14

            print "to new status:", status
            return status
        except Exception, e:
            print e
            return -1;

review_record_type_t = (
    ('n', u'无'),
#----------基本信息的审批记录类型
    ('b', u'外访信息'),
    ('t', u'三方信息'),
    ('c', u'面签信息'),
    ('i', u'身份信息'),
    ('p', u'身份证照片正面'),
    ('o', u'身份证照片反面'),
    ('q', u'手持身份证照片'),
    ('c', u'学籍信息'),
    ('f', u'联系人信息'),
    ('w', u'工作信息'),
    ('b', u'银行卡信息'),
    ('a', u'用户行为信息'),
)

review_record_status_t = (
    ('w', u'待上传'),
    ('r', u'打回修改'),
    ('y', u'通过 '),
    ('n', u'拒绝 '),
)

class ReviewRecord(models.Model):
    review_type = models.CharField(max_length=1, help_text="信息类型", default="n", choices=review_record_type_t)
    review_status = models.CharField(max_length=2, help_text="审批结果", default="n", choices=review_record_status_t)
    review_note = models.CharField(max_length=255, blank=True, null=True, help_text="审批注释")
    review_message = models.CharField(max_length=255, blank=True, null=True, help_text="返回用户提示")
    create_at = models.DateTimeField(auto_now_add=True)

    review = models.ForeignKey(Review)


label_type_t = (
    (0, "拒绝标签"),
    (1, "数据标签"),
)

sub_value_type_t = (
    (0, "---"),
    (1, "真实"),
    (2, "虚假"),
    (3, "未验证"),
    (4, "无目的"),
    (5, "有目的"),
    (6, "是"),
    (7, "否"),
)

model_type_t = (
    ('n', u'无'),
    ('id', u'身份信息'),
    ('front_pic', u'身份证照片正面'),
    ('back_pic', u'身份证照片反面'),
    ('hand_pic', u'手持身份证照片'),
    ('chsi', u'学籍信息'),
    ('contact', u'联系人信息'),
    ('work', u'工作信息'),
    ('bankcard', u'银行卡信息'),
    ('action', u'用户行为信息'),
)

class Label(models.Model):
    name = models.CharField(max_length=63, help_text="标签名称")
    label_id = models.IntegerField(help_text="标签id", unique=True)
    label_type = models.IntegerField(choices=label_type_t, help_text="标签类型")
    section = models.CharField(max_length=15, help_text="所属模块", default="none", choices=model_type_t)
    sub_value = models.IntegerField(default=0, choices=sub_value_type_t, help_text="数据标签的结果")

    def __unicode__(self):
        if self.sub_value == 0:
            return u'%d)%s - %s'%(self.label_id, self.get_section_display(), self.name)
        else:
            return u'%d)%s - %s:%s'%(self.label_id, self.get_section_display(), self.name, self.get_sub_value_display())

    def display(self):
        return self.__unicode__()

    def is_reject(self):
        if self.sub_value == 0 or self.sub_value == 2:
            return True
        else:
            return False

    @staticmethod
    def get_all_label():
        labels_all = Label.objects.all()
        labels = {"check":{}, "radio":{}}
        for label in labels_all:
            if label.label_type == 0:
                if not label.section in labels["check"]:
                    labels["check"][label.section] = []
                #labels["check"][label.section][label.name] = label.label_id
                sub_label = {}
                sub_label["name"] = label.name
                sub_label["value"] = label.label_id
                labels["check"][label.section].append(sub_label)
            elif label.label_type == 1:
                if not label.section in labels["radio"]:
                    labels["radio"][label.section] = {}
                if not label.name in labels["radio"][label.section]:
                    labels["radio"][label.section][label.name] = {}
                    sub_label = {}
                    sub_label["name"] = label.get_sub_value_display()
                    sub_label["value"] = label.label_id
                    sub_label["sub_value"] = label.sub_value
                    labels["radio"][label.section][label.name]["name"] = label.name
                    labels["radio"][label.section][label.name]["sub_value"] = [sub_label]
                else:
                    sub_label = {}
                    sub_label["name"] = label.get_sub_value_display()
                    sub_label["value"] = label.label_id
                    sub_label["sub_value"] = label.sub_value
                    labels["radio"][label.section][label.name]["sub_value"].append(sub_label)
                #labels["radio"][label.section][label.name].append(sub_label)
        #print labels
        return labels

#@receiver(post_migrate)#, sender=EmplyeePermission)
def gen_default_label(sender, **kwargs):
    #Label.objects.all().delete()
    Label(label_id=101, name="不符合进件政策", label_type=0, section='id').save()
    Label(label_id=102, name="冒名申请", label_type=0, section='id').save()
    #Label(label_id=102, name="家庭位置异常", label_type=1, section='id').save()
    Label(label_id=103, name="还款意愿差", label_type=0, section='id').save()
    Label(label_id=104, name="三方负面信息", label_type=0, section='id').save()
    Label(label_id=105, name="其他", label_type=0, section='id').save()

    Label(label_id=201, name="已离职", label_type=0, section='work').save()
    Label(label_id=202, name="单位虚假", label_type=0, section='work').save()
    Label(label_id=203, name="三方负面消息", label_type=0, section='work').save()
    #Label(label_id=100, name="工作位置异常", label_type=1, section='d').save()

    Label(label_id=301, name="父母是否虚假", label_type=1, section='contact', sub_value=1).save()
    Label(label_id=302, name="父母是否虚假", label_type=1, section='contact', sub_value=2).save()
    Label(label_id=304, name="联系人重复出现", label_type=0, section='contact').save()
    Label(label_id=305, name="代偿意愿差", label_type=0, section='contact').save()
    Label(label_id=306, name="多次无法确认", label_type=0, section='contact').save()
    Label(label_id=307, name="三方负面消息", label_type=0, section='contact').save()

    Label(label_id=308, name="催收通话记录", label_type=0, section='contact').save()
    Label(label_id=309, name="本人出现在通话记录", label_type=0, section='contact').save()
    Label(label_id=310, name="与父母无联系", label_type=0, section='contact').save()
    Label(label_id=311, name="无通讯录、通话记录、详单", label_type=0, section='contact').save()
    Label(label_id=312, name="与多家贷款公司联系异常", label_type=0, section='contact').save()
    Label(label_id=314, name="详单是否虚假", label_type=1, section='contact', sub_value=1).save()
    Label(label_id=315, name="详单是否虚假", label_type=1, section='contact', sub_value=2).save()
    Label(label_id=316, name="电话实名不匹配", label_type=0, section='contact').save()

    Label(label_id=401, name="机器ID重复", label_type=0, section='action').save()
    Label(label_id=402, name="借款目的", label_type=1, section='action', sub_value=4).save()
    Label(label_id=403, name="借款目的", label_type=1, section='action', sub_value=5).save()
    Label(label_id=405, name="是否容许再进件", label_type=1, section='action', sub_value=6).save()
    Label(label_id=406, name="是否容许再进件", label_type=1, section='action', sub_value=7).save()

    Label(label_id=501, name="和他人银行卡重复", label_type=0, section='bankcard').save()

    Label(label_id=601, name="身份证虚假", label_type=0, section='front_pic').save()

    Label(label_id=701, name="身份证虚假", label_type=0, section='back_pic').save()

    Label(label_id=801, name="身份证虚假", label_type=0, section='hand_pic').save()

    Label(label_id=901, name="学信网问题", label_type=0, section='chsi').save()
    Label(label_id=902, name="电商数据问题", label_type=0, section='chsi').save()


class BankStatement(models.Model):
    status_choices = (
        (0, '还款成功'),
        (1, '预扣款'),
        (2, '还款失败'),
    )
    apply = models.ForeignKey(Apply)
    bankcard = models.ForeignKey(BankCard)
    user = models.ForeignKey(User)

    pre_order_number = models.CharField(max_length=255, help_text="预扣款账单号")
    order_number = models.CharField(max_length=255, blank=True, null=True, help_text="账单号")
    content = models.CharField(max_length=255, blank=True, null=True, help_text="内容")
    real_repay_amount = models.IntegerField(blank=True, null=True, help_text='实际还款金额')
    status = models.IntegerField(choices=status_choices, help_text="状态")
    installment_number = models.CharField(max_length=255, blank=True, null=True, help_text="贷款期数,使用 , 号分割")

    update_at = models.DateTimeField(default=datetime.datetime.now)
    create_at = models.DateTimeField(auto_now_add=True)

class CollectionRecord(models.Model):

    COLLECTION = '0'
    MESSAGE = '1'
    REPAY = '2'
    DISPATCH = '3'
    DISCOUNT = '4'
    COMMENT = '5'
    CHECK_BACK = '6'
    CHECK_NOTES = '7'
    LOST_CONTACT = '8'
    collection_record_type_t = (
        (COLLECTION, u'催记'),
        (MESSAGE, u'短信'),
        (REPAY, u'扣款'),
        (DISPATCH, u'分配'),
        (DISCOUNT, u'减免'),
        (COMMENT, u'备注'),
        (CHECK_BACK, u'财务打回'),
        (CHECK_NOTES, u'财务备注'),
        (LOST_CONTACT, u'失联'),
    )

    SELF = '0'
    THIRD = '1'
    OTHER = '2'
    object_type_t = (
        (SELF, u'本人'),
        (THIRD, u'三方'),
        (OTHER, u'其它'),
    )

    record_type = models.CharField(max_length=1, help_text="信息类型", default="0", choices=collection_record_type_t)
    object_type = models.CharField(max_length=15, help_text="催收对象", default="0", choices=object_type_t)
    collection_note = models.CharField(max_length=1024, blank=True, null=True, help_text="催收注释")
    promised_repay_time = models.DateTimeField(help_text="承诺还款时间", blank=True, null=True)
    create_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(Employee, help_text="催收人员")
    apply = models.ForeignKey(Apply)

    check_apply = models.ForeignKey(CheckApply, blank=True, null=True)

    installment_numbers = models.CharField(max_length=255, help_text="逾期期数", default="0")
    overdue_days = models.IntegerField(help_text="逾期天数", default=0)
    should_repay_amount = models.IntegerField(help_text="应还金额", default=0)
    ori_should_repay_amount = models.IntegerField(help_text="委案金额", default=0)

    message_template = models.ForeignKey(Messagetemplate, blank=True, null=True)

    status = models.IntegerField(default=0, choices=status_choices)

    def __unicode__(self):
        return u'%s)%s - %s'%(self.create_by.username ,self.apply.create_by.name, self.get_record_type_display())


class RepayRecord(models.Model):
    '''实际扣款分期记录

    RepayRecord 的详细记录, 依据 分期 进行分发.
    当 还款 <= 当期应还款 时, 只有一条记录, 数据与 RepayRecord 相同
    当 还款 > 当期应还款 时, 多条记录, 数据之和与 RepayRecord 相同


    '''
    exact_amount = models.IntegerField(help_text="实还总额")
    exact_principle = models.IntegerField(default=0, help_text="实还本金")
    exact_interest = models.IntegerField(default=0, help_text="实还利息")
    exact_fee = models.IntegerField(default=0, help_text="实还服务费")
    exact_overdue_interest = models.IntegerField(default=0, help_text="实还罚息")
    exact_penalty = models.IntegerField(default=0, help_text="实还罚金")
    exact_bank_fee = models.IntegerField(default=0, help_text="实还手续费（银联）")

    status = models.IntegerField(default=0, help_text="扣款状态")
    repay_channel = models.IntegerField(default=0, help_text="扣款状态")

    bank_card = models.ForeignKey(BankCard, null=True, blank=True, help_text="还款的银行卡", related_name="bank_card_id")
    repayment = models.ForeignKey(RepaymentInfo, help_text="对应借款记录", related_name="repayment_id")

    create_at = models.DateTimeField()

    class Meta:
        db_table = u'repayrecord'


class RepayInstallmentRecord(models.Model):
    '''实际扣款分期记录

    RepayRecord 的详细记录, 依据 分期 进行分发.
    当 还款 <= 当期应还款 时, 只有一条记录, 数据与 RepayRecord 相同
    当 还款 > 当期应还款 时, 多条记录, 数据之和与 RepayRecord 相同


    '''
    repay_record = models.ForeignKey(RepayRecord, help_text="实际扣款记录", related_name="repay_record_id")
    exact_amount = models.IntegerField(help_text="实还总额")
    exact_principle = models.IntegerField(default=0, help_text="实还本金")
    exact_interest = models.IntegerField(default=0, help_text="实还利息")
    exact_fee = models.IntegerField(default=0, help_text="实还服务费")
    exact_overdue_interest = models.IntegerField(default=0, help_text="实还罚息")
    exact_penalty = models.IntegerField(default=0, help_text="实还罚金")
    exact_bank_fee = models.IntegerField(default=0, help_text="实还手续费（银联）")

    status = models.IntegerField(default=0, help_text="扣款状态")
    repay_channel = models.IntegerField(default=0, help_text="扣款状态")

    bank_card = models.ForeignKey(BankCard, null=True, blank=True, help_text="还款的银行卡", related_name="bank_card_id2")
    repayment = models.ForeignKey(RepaymentInfo, help_text="对应借款记录", related_name="repayment_id2")
    installment = models.ForeignKey(InstallmentDetailInfo, help_text="对应扣款", related_name="installment_id")

    create_at = models.DateTimeField()

    class Meta:
        db_table = u'repayinstallmentrecord'


class DingdangRepayRecord(models.Model):
    """叮当回款记录, 对应 installment"""
    real_repay_amount = models.IntegerField(help_text="还款金额")
    real_repay_time = models.DateTimeField()
    repayment_order_number = models.IntegerField(help_text="贷款工单号")
    installment_order_number = models.IntegerField(help_text="期款工单号")
    apply_time = models.DateTimeField(blank=True, null=True, help_text="不知道什么意思")
    apply = models.ForeignKey(Apply)
    collector = models.ForeignKey(Employee,blank=True, null=True, help_text="催收人员")

    update_at = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)

class DingdangRepaymentRecord(models.Model):
    """叮当进件记录, 对应 repayment"""

    overdue_types = (
        ('a', 'm0'),
        ('b', 'm1'),
        ('c', 'm2'),
        ('d', 'm3'),
        ('e', 'm4'),
        ('g', 'm5'),
        ('h', 'm5+'),
    )
    types = (
        (0, '委案'),
        (1, '更新'),
        (-1, '无效数据'),
    )

    apply = models.ForeignKey(Apply, blank=True, null=True)
    collector = models.ForeignKey(Employee, blank=True, null=True, help_text="催收人员")
    type = models.IntegerField(choices=types, help_text='类型')
    installment_order_number = models.CharField(max_length=255, help_text='最近一期的工单号')
    should_repay_amount = models.IntegerField(default=0, help_text='当前应还金额')
    overdue_type = models.CharField(choices=overdue_types, max_length=2, help_text='催收类型')
    overdue_days = models.IntegerField(default=0, help_text='当前逾期天数')

    order_number = models.CharField(max_length=255, help_text='订单号') # 订单号，全局唯一
    # 进件时 installment_info 中包含的 分期数据条数
    latest_installment_count = models.IntegerField(default=0, help_text='贷款期数条数')
    installment_count = models.IntegerField(default=0, help_text='贷款期数')
    strategy_id = models.IntegerField(default=0, help_text='贷款策略,叮当的.暂时没用')

    # repay_status = models.IntegerField(choices=repay_status_type_t, help_text='还款状态')
    apply_amount = models.IntegerField(default=0, help_text='申请金额')
    exact_amount = models.IntegerField(default=0, help_text='实际打款金额')
    real_repay_amount = models.IntegerField(default=0, help_text='已还需还金额')
    rest_amount = models.IntegerField(default=0, help_text='剩余未还金额')


    user_name = models.CharField(max_length=255, help_text='用户名')
    id_no = models.CharField(max_length=255, help_text='用户身份证')
    phone_no = models.CharField(max_length=255, help_text='手机号码')
    channel = models.CharField(max_length=255, help_text='渠道')

    bank_card_number = models.CharField(max_length=255, help_text='银行卡号')
    bank_card_name = models.CharField(max_length=255, help_text='银行名称')

    apply_time = models.DateTimeField(blank=True, null=True, help_text='申请时间')

    update_at = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u'%d)%s'%(self.id, self.user_name)


class CollectionRecordTag(models.Model):
    """催记标签

    催记 的额外信息
    """
    # 电话接通状态
    call_status_choices = (
        (0, u'接通'),
        (1, u'关机'),
        (2, u'停机'),
        (3, u'空号'),
        (4, u'未接听'),
        (5, u'挂掉'),
    )
    # 催收对象
    collection_type_choices = (
        (0, u'本人'),
        (1, u'联系人'),
        (2, u'信修召回'),
    )
    xinxiu_type_choices = (
        (0, u'本人'),
        (1, u'联系人'),
        (2, u'不相关'),
    )
    # 用户态度
    user_attitude_choices = (
        (0, u'积极配合'),
        (1, u'一般'),
        (2, u'不配合'),
    )
    # 还款意愿
    repay_attitude_choices = (
        (0, u'承诺还款'),
        (1, u'未承诺还款'),
        (2, u'欺诈恶意拖欠'),
    )
    # 联系人真实性
    contactor_truth_choices = (
        (0, u'虚假'),
        (1, u'真实'),
    )
    # 联系人态度
    contactor_attitude_choices = (
        (0, u'事不关己'),
        (1, u'有代偿意愿'),
        (2, u'代为通知'),
    )
    # 联系人有无负面信息
    contactor_negative_info_choices = (
        (0, u'无'),
        (1, u'有'),
    )

    call_status = models.IntegerField(help_text="电话接通状态", default=0, choices=call_status_choices)
    collection_type = models.IntegerField(help_text="催收对象", default=0, choices=collection_type_choices)

    xinxiu_type = models.IntegerField(help_text="信修对象", default=2, choices=xinxiu_type_choices)

    user_attitude = models.IntegerField(help_text="用户态度", default=0, choices=user_attitude_choices)
    repay_attitude = models.IntegerField(help_text="还款意愿", default=0, choices=repay_attitude_choices)
    promised_repay_time = models.DateTimeField(help_text="承诺还款时间", blank=True, null=True)
    overdue_note = models.CharField(max_length=1024, blank=True, null=True, help_text="拖欠原因")

    contactor_truth = models.IntegerField(help_text="联系人真实性", default=1, choices=contactor_truth_choices)
    contactor_attitude = models.IntegerField(help_text="联系人态度", default=0, choices=contactor_attitude_choices)
    contactor_negative_info = models.IntegerField(help_text="联系人有无负面信息", default=0, choices=contactor_negative_info_choices)
    negative_info_note = models.CharField(max_length=1024, blank=True, null=True, help_text="负面信息")

    collection_note = models.CharField(max_length=1024, blank=True, null=True, help_text="催收注释")
    collection_record = models.OneToOneField(CollectionRecord, help_text='催记', related_name='tag')

    status = models.IntegerField(default=0, choices=status_choices)
    update_at = models.DateTimeField(auto_now_add=True)

    create_at = models.DateTimeField(auto_now_add=True)

    # class Meta:
        # db_table = u'collection_record_tag'


class AppointRepaymentRecord(models.Model):
    """进件记录. 对应 installment"""

    overdue_type_choices = (
        ('a', 'm0'),
        ('b', 'm1'),
        ('c', 'm2'),
        ('d', 'm3'),
        ('e', 'm4'),
        ('g', 'm5'),
        ('h', 'm5+'),
    )
    status_choices = (
        (0, '正常数据'),
        # (1, '更新'),
        # parent_id 不为空
        (1, '子数据'),
        (-1, '无效数据'),
    )

    apply = models.ForeignKey(Apply)
    collector = models.ForeignKey(Employee, blank=True, null=True, help_text="催收人员")
    installment_id = models.IntegerField(help_text='')
    should_repay_amount = models.IntegerField(default=0, help_text='应还金额')
    should_repay_time = models.DateTimeField(help_text='应还时间')
    overdue_type = models.CharField(choices=overdue_type_choices, max_length=2, help_text='催收类型')
    overdue_days = models.IntegerField(default=0, help_text='逾期天数')

    repayment_id = models.IntegerField(help_text='')
    # 进件时 installment_info 中包含的 分期数据条数
    # latest_installment_count = models.IntegerField(default=0, help_text='贷款期数条数')
    # installment_count = models.IntegerField(default=0, help_text='贷款期数')
    strategy_id = models.IntegerField(default=0, help_text='贷款策略')

    # repay_status = models.IntegerField(choices=repay_status_type_t, help_text='还款状态')
    apply_amount = models.IntegerField(default=0, help_text='申请金额')
    # exact_amount = models.IntegerField(default=0, help_text='实际打款金额')
    # real_repay_amount = models.IntegerField(default=0, help_text='已还需还金额')
    # rest_amount = models.IntegerField(default=0, help_text='剩余未还金额')


    id_no = models.CharField(max_length=255, help_text='用户身份证')
    channel = models.CharField(max_length=255, help_text='渠道')
    user_name = models.CharField(max_length=255, help_text='用户名')
    phone_no = models.CharField(max_length=255, help_text='手机号码')

    # bank_card_number = models.CharField(max_length=255, help_text='银行卡号')
    # bank_card_name = models.CharField(max_length=255, help_text='银行名称')

    # apply_time = models.DateTimeField(blank=True, null=True, help_text='申请时间')
    # 逾期多期的时候, 是否属于同一笔委案
    parent_id = models.IntegerField(blank=True, null=True)

    platform = models.CharField(max_length = 64, blank = True)
    product = models.CharField(max_length = 64, blank = True)
    update_at = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)
    status = models.IntegerField(choices=status_choices, default=0, help_text='类型')

    def __unicode__(self):
        return u'%d)%s'%(self.id, self.user_name)


