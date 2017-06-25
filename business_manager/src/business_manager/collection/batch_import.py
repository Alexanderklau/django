# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext,Template
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.db import models
from django.views.decorators.http import require_http_methods


from ..order.apply_models import Apply, CheckApply
from ..order.models import BankCard, ContactInfo, CheckStatus, User, Profile, IdCard
from ..review.models import DingdangRepayRecord, CollectionRecord, DingdangRepaymentRecord
from ..collection.models import *
from ..collection.strategy import *
# from business_manager.review import user_center_client
from ..user_center.user_center_client import UserCenterClient
from ..import_data.services import report_data_collection_money, trans_to_inner_field
from ..python_common.log_client import CommonLog as Log

import re
import time
import json
import traceback
import httplib
import urllib2
from datetime import datetime
import sys
import time
import poplib
import smtplib
from email.mime.text import MIMEText

import arrow


user_center_client = UserCenterClient(settings.USER_CENTER_SERVER['HOST'], settings.USER_CENTER_SERVER['PORT'], 2000)

#邮件发送函数
def send_mail(title, msg):
    print 'in send_mail'
    # handle = smtplib.SMTP('smtp.aliyun.com',25)
    handle = smtplib.SMTP('smtp.mxhichina.com',25)
    handle.login('dengzhehao@rongshutong.com', '123mint!')
    # msg = 'To: XXXX@qq.com\r\nFrom:XXXX@126.com\r\nSubject:hello\r\n'
    print msg.encode('utf-8')
    msg = MIMEText(str(msg.encode('utf-8')))
    msg["Subject"] = str(title.encode('utf-8'))
    msg["To"] = 'dengzhehao@rongshutong.com\r\n'
    handle.sendmail('dengzhehao@rongshutong.com','dengzhehao@rongshutong.com',msg.as_string())
    handle.close()
    print 'out send_mail'
    return 1



M1 = 30
M2 = 60
M3 = 90
M4 = 120
M5 = 150

def get_collection_type(overdue_days):
    """逾期类型 M1, M2, M3, M3+"""
    data = Apply.COLLECTION_M0
    if overdue_days > M5:
        data = Apply.COLLECTION_M6
    elif overdue_days > M4:
        data = Apply.COLLECTION_M5
    elif overdue_days > M3:
        data = Apply.COLLECTION_M4
    elif overdue_days > M2:
        data = Apply.COLLECTION_M3
    elif overdue_days > M1:
        data = Apply.COLLECTION_M2
    else:
        data = Apply.COLLECTION_M1

    return data


class ImportError(Exception):
    '''
        数据导入专用异常
    '''
    EC_SUCCESS = 0
    EC_LACK = 21000
    EC_NULL = 21001
    EC_ILLAGAL = 21002
    EC_DUP = 21003
    EC_JSON = 21004
    EC_DB = 21005
    EC_INTERNAL = 21100

    errors = {
        EC_SUCCESS :{"error_code" : EC_SUCCESS, "error_msg" : u"成功", "error_detail" : ""},
        EC_LACK :{"error_code" : EC_LACK, "error_msg" : u"字段缺失", "error_detail" : "请检查%s字段是否存在"},
        EC_NULL :{"error_code" : EC_NULL, "error_msg" : u"字段不能为空", "error_detail" : "请检查%s字段是否为空"},
        EC_ILLAGAL :{"error_code" : EC_ILLAGAL, "error_msg" : u"字段不合法", "error_detail" : "%s字段格式非法"},
        EC_DUP :{"error_code" : EC_DUP, "error_msg" : u"主键重复", "error_detail" : "%s字段主键重复，无法导入"},
        EC_JSON :{"error_code" : EC_JSON, "error_msg" : u"json格式错误", "error_detail" : "%s"},
        EC_INTERNAL :{"error_code" : EC_INTERNAL, "error_msg" : u"内部错误", "error_detail" : "%s"},
        EC_DB :{"error_code" : EC_DB, "error_msg" : u"写数据失败", "error_detail" : "%s"},
    }

    def __init__(self, error_no, msg):
        self._error_no = error_no
        self._msg = self.errors[error_no]["error_msg"]
        self._error_detail = self.errors[error_no]["error_detail"] % (msg)

    def get_error(self, name=""):
        error = {}
        error["error_no"] = self._error_no
        error["error_msg"] = self._msg
        error["error_detail"] = self._error_detail
        if name != "":
            error["name"] = name
        return error

    def get_ec(self):
        return self._error_no

    def get_response(self):
        error_list = []
        ret_json = {}
        if self.get_ec() != 0:
            error_list.append(self.get_error())
            ret_json["success"] = False
            ret_json['success_num'] = 0
            ret_json['fail_num'] = 1
        else:
            ret_json["success"] = True
            ret_json['success_num'] = 1
            ret_json['fail_num'] = 0
        ret_json["error_list"] = error_list
        return HttpResponse(json.dumps(ret_json, ensure_ascii=False))

    def __str__(self):
        return json.dumps(self.get_error(), ensure_ascii=False)

def trans_to_cent(d):
    '''
        把钱变成分
    '''
    try:
        if type(d) == str or type(d) == unicode:
            return int(float(d) * 100)
        elif type(d) == int:
            return (d * 100)
        elif type(d) == float:
            return int(d * 100)
        else:
            print "unknown type, ", type(d)
            return 0
    except Exception, e:
        traceback.print_exc()
        print e
        raise ImportError(ImportError.EC_NUMBER, "非法数字 %s" % str(e))


def check_phone(s):
    '''
        电话号码校验
    '''
    #号码前缀，如果运营商启用新的号段，只需要在此列表将新的号段加上即可。
    #phoneprefix=['130','131','132','133','134','135','136','137','138','139','150','151','152','153','156','158','159','170','183','182','185','186','188','189']
    phoneprefix=['1']
    #检测号码是否长度是否合法。
    if len(s)<>11:
        raise ImportError(ImportError.EC_ILLAGAL, "验证手机号过程错误,手机号长度有误")
    else:
        #检测输入的号码是否全部是数字。
        if s.isdigit():
            #检测前缀是否是正确。
            if s[:1] in phoneprefix:
                return True
        raise ImportError(ImportError.EC_ILLAGAL, "验证手机号过程错误,手机号格式有误")

def check_id_card(idcard):
    '''
        身份证号码校验
    '''
    try:
        Errors=['验证通过!','身份证号码位数不对!','身份证号码出生日期超出范围或含有非法字符!','身份证号码校验错误!','身份证地区非法!']
        area={"11":"北京","12":"天津","13":"河北","14":"山西","15":"内蒙古","21":"辽宁","22":"吉林","23":"黑龙江","31":"上海","32":"江苏","33":"浙江","34":"安徽","35":"福建","36":"江西","37":"山东","41":"河南","42":"湖北","43":"湖南","44":"广东","45":"广西","46":"海南","50":"重庆","51":"四川","52":"贵州","53":"云南","54":"西藏","61":"陕西","62":"甘肃","63":"青海","64":"宁夏","65":"新疆","71":"台湾","81":"香港","82":"澳门","91":"国外"}
        idcard=str(idcard)
        idcard=idcard.strip()
        idcard_list=list(idcard)
        #地区校验
        if(not area[(idcard)[0:2]]):
            raise ImportError(ImportError.EC_ILLAGAL, Errors[4])
        #15位身份号码检测
        if(len(idcard)==15):
            if((int(idcard[6:8])+1900) % 4 == 0 or((int(idcard[6:8])+1900) % 100 == 0 and (int(idcard[6:8])+1900) % 4 == 0 )):
                erg=re.compile('[1-9][0-9]{5}[0-9]{2}((01|03|05|07|08|10|12)(0[1-9]|[1-2][0-9]|3[0-1])|(04|06|09|11)(0[1-9]|[1-2][0-9]|30)|02(0[1-9]|[1-2][0-9]))[0-9]{3}$')#//测试出生日期的合法性
            else:
                ereg=re.compile('[1-9][0-9]{5}[0-9]{2}((01|03|05|07|08|10|12)(0[1-9]|[1-2][0-9]|3[0-1])|(04|06|09|11)(0[1-9]|[1-2][0-9]|30)|02(0[1-9]|1[0-9]|2[0-8]))[0-9]{3}$')#//测试出生日期的合法性
            if(re.match(ereg,idcard)):
                return Errors[0]
            else:
                raise ImportError(ImportError.EC_ILLAGAL, Errors[2])
        #18位身份号码检测
        elif(len(idcard)==18):
            #出生日期的合法性检查
            #闰年月日:((01|03|05|07|08|10|12)(0[1-9]|[1-2][0-9]|3[0-1])|(04|06|09|11)(0[1-9]|[1-2][0-9]|30)|02(0[1-9]|[1-2][0-9]))
            #平年月日:((01|03|05|07|08|10|12)(0[1-9]|[1-2][0-9]|3[0-1])|(04|06|09|11)(0[1-9]|[1-2][0-9]|30)|02(0[1-9]|1[0-9]|2[0-8]))
            if(int(idcard[6:10]) % 4 == 0 or (int(idcard[6:10]) % 100 == 0 and int(idcard[6:10])%4 == 0 )):
                ereg=re.compile('[1-9][0-9]{5}19[0-9]{2}((01|03|05|07|08|10|12)(0[1-9]|[1-2][0-9]|3[0-1])|(04|06|09|11)(0[1-9]|[1-2][0-9]|30)|02(0[1-9]|[1-2][0-9]))[0-9]{3}[0-9Xx]$')#//闰年出生日期的合法性正则表达式
            else:
                ereg=re.compile('[1-9][0-9]{5}19[0-9]{2}((01|03|05|07|08|10|12)(0[1-9]|[1-2][0-9]|3[0-1])|(04|06|09|11)(0[1-9]|[1-2][0-9]|30)|02(0[1-9]|1[0-9]|2[0-8]))[0-9]{3}[0-9Xx]$')#//平年出生日期的合法性正则表达式
            #//测试出生日期的合法性
            if(re.match(ereg,idcard)):
                #//计算校验位
                S = (int(idcard_list[0]) + int(idcard_list[10])) * 7 + (int(idcard_list[1]) + int(idcard_list[11])) * 9 + (int(idcard_list[2]) + int(idcard_list[12])) * 10 + (int(idcard_list[3]) + int(idcard_list[13])) * 5 + (int(idcard_list[4]) + int(idcard_list[14])) * 8 + (int(idcard_list[5]) + int(idcard_list[15])) * 4 + (int(idcard_list[6]) + int(idcard_list[16])) * 2 + int(idcard_list[7]) * 1 + int(idcard_list[8]) * 6 + int(idcard_list[9]) * 3
                Y = S % 11
                M = "F"
                JYM = "10X98765432"
                M = JYM[Y]#判断校验位
                if(M == idcard_list[17] or (M == "X" and idcard_list[17]== "x")):#检测ID的校验位
                    return Errors[0]
                else:
                    raise ImportError(ImportError.EC_ILLAGAL, Errors[3])
            else:
                raise ImportError(ImportError.EC_ILLAGAL, Errors[2])
        else:
            raise ImportError(ImportError.EC_ILLAGAL, Errors[1])
    except Exception, e:
        print e
        traceback.print_exc()
        raise ImportError(ImportError.EC_INTERNAL, "身份证验证出错")

def check_param_none(req, param):
    if req[param] == None or req[param] == "" or req[param] == "null":
        raise ImportError(ImportError.EC_NULL, param)

def check_parameter(d, required_set, optional_set):
    for k in required_set:
        if k not in d:
            raise ImportError(ImportError.EC_LACK, k)
    for k in optional_set:
        if k not in d:
            d[k] = ""

def ensure_card_info_has_key(d):
    required_set =  ["card_number", "bank_type", "card_type"]
    optional_set = [""]
    check_parameter(d, required_set, optional_set)

def ensure_user_info_has_key(d):
    required_set = ["id_no", "phone_no", "name", "channel"]
    optional_set = ["work_address", "work_name", "home_number", "home_address", "register_time", "marriage"]
    check_parameter(d, required_set, optional_set)

def ensure_repayment_info_has_key(d):
    required_set = ["repayment_id", "amount", "apply_time", "pay_time", "installment_info"]
    optional_set = []
    check_parameter(d, required_set, optional_set)

def ensure_contact_info_have_need_key(d):
    required_set = ["phone_no", "name", "relationship"]
    optional_set = []
    check_parameter(d, required_set, optional_set)

def check_none(d):
    for k in d:
        if type(d[k]) == dict:
            check_none(d[k])
        if not d[k]:
            raise ImportError(ImportError.EC_NULL, k)

def gen_checkstatus(u):
    old_status = CheckStatus.objects.filter(Q(owner = u))
    if len(old_status) == 0:
        c = CheckStatus(owner=u, apply_status=CheckStatus.APPROVAL, profile_status=16405, profile_check_status=16405, credit_limit=100000, real_id_verify_status=5, auto_check_status=0)
        c.save()


def get_gender(id_number):
    '''
        身份证获取性别
    '''
    #之前已经验证过身份证号有效性了
    gender = id_number[-2]
    if gender in ("1", "3", "5", "7", "9"):
        return Profile.MALE
    elif gender in ("2", "4", "6", "8", "0"):
        return Profile.FEMALE
    else:
        return Profile.UNKNOWN

def get_days(days):
    try:
        return int(days)
    except Exception, e:
        return 0

def get_marriage(marriage):
    if marriage == u"未婚" or marriage == 1:
        return Profile.SINGLE
    elif marriage == u"已婚" or marriage == 2:
        return Profile.MARRIED
    elif marriage == u"已婚无子女":
        #return Profile.MARRIED_NO_CHILD
        return Profile.MARRIED
    elif marriage == u"已婚有子女":
        #return Profile.MARRIED_HAS_CHILD
        return Profile.MARRIED
    elif marriage == u"离异":
        #return Profile.DIVORCED
        return Profile.SINGLE
    elif marriage == u"丧偶":
        #return Profile.WIDOWS
        return Profile.SINGLE
    return Profile.UNKNOWN

def gen_profile_info(data, u):
    if data.has_key('user_info'):
        info = data["user_info"]
        try:
            p = u.profile
            p.gender=get_gender(info["id_no"])
            p.job=Profile.UNKNOWN
            p.marriage=get_marriage(info["marriage"])
            #p.company=info["work_name"]
            p.company_phone=info["work_number"],
            p.family_address=(info["home_address"])
            p.work_address=(info["work_address"])
            p.email=info["email"]
            p.save()
        except Profile.DoesNotExist, e:
            p = Profile(owner=u, gender=get_gender(info["id_no"]), job=Profile.UNKNOWN, marriage=get_marriage(info["marriage"]),
                    company="", work_post="", company_phone=info["work_number"],
                    family_address=(info["home_address"]), work_address=(info["work_address"]), email=info["email"], qq="")
            p.save()
        #print "gen profile success"
    else:
        p = Profile()
        p.save()

def get_relationship(relationship):
    if relationship == u"父亲":
        return ContactInfo.FATHER
    elif relationship == u"母亲":
        return ContactInfo.MOTHER
    elif relationship == u"亲戚":
        return ContactInfo.RELATIVE
    elif relationship == u"配偶":
        return ContactInfo.MATE
    elif relationship == u"朋友":
        return ContactInfo.FRIEND
    elif relationship == u"同事":
        return ContactInfo.WORKMATE
    elif relationship == u"同学":
        return ContactInfo.CLASSMATE
    return ContactInfo.UNKNOWN

def gen_idcard(data, user):
    # "idcard":{"front_pic": "front_pic", "back_pic": "bank_pic", "handle_pic": "handle_pic"},
    try:
        print "gen idcard"
        ori_id_data = data["user_info"].get("id_card")
        if not ori_id_data:
            return
        id_data = dict(
            front_pic=ori_id_data.get('front_pic', '') or '',
            back_pic=ori_id_data.get('back_pic', '') or '',
            handle_pic=ori_id_data.get('handle_pic', '') or '',
            owner=user,
        )
        idcard = IdCard.objects.filter(owner=user)
        print idcard
        if idcard:
            idcard.update(**id_data)
        else:
            idcard = IdCard(**id_data)
            idcard.save()
        print "gen idcard success"
        print idcard
    except Exception, e:
        print e
        traceback.print_exc()
        # raise ImportError(ImportError.EC_DB, "idcard save failed: %s" % str(e))
        Log().error("idcard save failed: %s" % str(e))


#这里分配一个前缀号段 表示一个渠道 而且能避免user 信息重复导入
def gen_user_and_contacts(data, org_account=None):
    try:
        user_info = data["user_info"]
        ensure_user_info_has_key(user_info)
        #check_none(user_info)
        check_id_card(user_info['id_no'])
        check_phone(user_info['phone_no'])

        u = None
        users = User.objects.filter(Q(channel = user_info["channel"]) & Q(phone_no = user_info['phone_no']) & Q(platform=org_account))
        if (users.count() > 1):
            raise ImportError(ImportError.EC_DUP, "%s,%s多个重复用户" % (channel, user_info['phone_no']))
        elif users.count() == 1:
            u = users[0]
            u.name = user_info["name"]
            u.phone_no = user_info["phone_no"]
            u.id_no = user_info["id_no"]
            u.channel = user_info["channel"]
            u.platform = org_account
            u.create_time = get_date(user_info["register_time"])
        else:
            try:
                u = User()
                u.name = user_info["name"]
                u.password = "e10adc3949ba59abbe56e057f20f883e"
                u.phone_no = user_info["phone_no"]
                u.id_no = user_info["id_no"]
                u.channel = user_info["channel"]
                u.platform = org_account
                u.create_time = get_date(user_info["register_time"])
                u.is_register = 1
                u.save()
                print "user gen success", u
            except Exception, e:
                print e
                traceback.print_exc()
                raise ImportError(ImportError.EC_DB, "user save failed: %s" % str(e))

        gen_profile_info(data, u)
        print "gen profile"
        gen_idcard(data, u)
        #
        try:
            gen_checkstatus(u)
            print "gen checkstatus"
        except Exception , e:
            traceback.print_exc()
            raise ImportError(ImportError.EC_DB, "profile or checkstatus save failed: %s" % str(e))

        for i in data["user_info"]["contact_list"]:
            ensure_contact_info_have_need_key(i)
            #check_phone(i['phone_no'])
            #contact_next_id = ContactInfo.objects.all().order_by("-id")[0].id + 1
            #i["id"] = contact_next_id
            i["owner_id"] = u.id
            try:
                # if non
                contact_exist = ContactInfo.objects.filter(owner=u, phone_no=i["phone_no"][0:12])
                if not contact_exist:
                    c = ContactInfo(owner=u, name=i["name"], relationship=get_relationship(i["relationship"]), phone_no=i["phone_no"][0:12])
                    c.save()
                    print "save contact " , i
            except Exception, e:
                traceback.print_exc()
                raise ImportError(ImportError.EC_DB, "contacts save failed: %s" % str(e))
        return u
    except ImportError, e:
        raise e
    except Exception, e:
        print e
        traceback.print_exc()
        raise ImportError(ImportError.EC_INTERNAL, str(e))

def get_bank_type(bank_type):
    if bank_type == u"建设银行":
        return 1
    elif bank_type == u"中国银行":
        return 2
    elif bank_type == u"农业银行":
        return 3
    elif bank_type == u"招商银行":
        return 4
    elif bank_type == u"广发银行":
        return 5
    elif bank_type == u"兴业银行":
        return 6
    elif bank_type == u"工商银行":
        return 7
    elif bank_type == u"光大银行":
        return 8
    elif bank_type == u"中国邮政储蓄" or bank_type == u"邮政储蓄银行":
        return 9
    return 0

def gen_card_info(data, u):
    card_info = data["card_info"]
    try:
        return BankCard.objects.get(Q(card_number = card_info['card_number']) & Q(owner = u) & Q(card_type__in = [2,3]))
    except BankCard.DoesNotExist:
        pass
    try:
        ensure_card_info_has_key(card_info)
        #check_none(card_info)
        #c = BankCard()
        if card_info.has_key("card_type"):
            c = BankCard.objects.create(card_number=card_info['card_number'],
                                        bank_type=get_bank_type(card_info['bank_type']), owner = u, bank_name=card_info['bank_type'],
                card_type= card_info['card_type'])
        else:
            c = BankCard.objects.create(card_number=card_info['card_number'],
                                        bank_type=get_bank_type(card_info['bank_type']), owner = u, bank_name=card_info['bank_type'])
        c.save()
        return c
    except ImportError, e:
        raise e
    except Exception, e:
        traceback.print_exc()
        print e
        raise ImportError(ImportError.EC_DB, "save card failed" % str(e))

def get_date(t):
    try:
        if len(t) == 10:
            d = datetime.strptime(t, "%Y-%m-%d")
        elif len(t) == 19:
            d = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
        else:
            d = datetime.strptime(t, "%b %d, %Y %I:%M:%S %p")
        return d
    except:
        return datetime.now()

def gen_installs_info(repayment, installment_info, org_account):
    print 'in gen_installs_info'
    # 未还本金, 只在下面的 loop 中使用
    day = repayment.first_repay_day
    _rest_principle = repayment.apply_amount

    # exists_installment = InstallmentDetailInfo.objects.filter(Q(repayment=repayment))
    # if len(exists_installment) == 0:
        # # 生成每一期的还款
        # for i in range(1, strategy.installment_count + 1):
            # principle_and_interest = strategy.get_principle_and_interest(repayment.apply_amount)
            # should_repay_amount = strategy.get_installment_amount(repayment.apply_amount, i)
            # repay_interest = int(_rest_principle * strategy.interest)
            # repay_principle = int(principle_and_interest - repay_interest)
            # repay_fee = strategy.get_installment_factorage(repayment.apply_amount)
            # detail = InstallmentDetailInfo(
                # repayment=repayment,
                # installment_number=i,
                # should_repay_time=str(strategy.get_installment_date(i, day,False)),
                # real_repay_time=None,
                # should_repay_amount=should_repay_amount,
                # repay_principle=repay_principle,
                # repay_interest=repay_interest,
                # repay_fee=repay_fee,
                # real_repay_amount=0,
                # repay_status=RepaymentInfo.PRE_DONE,
                # repay_channel=0,
                # repay_overdue=0,
                # reduction_amount=0,
                # repay_overdue_interest=0,
                # repay_penalty=0,
                # repay_bank_fee=0,
                # overdue_days=0,
            # )
            # _rest_principle -= repay_principle
            # detail.save()

    # 更新还款生成appky
    max_id = 0
    max_overdue_days = 0
    rest_repay_money = 0
    # 委案金额, 逾期类型转变时, 更新
    ori_collection_amount = 0
    first_repay_day = arrow.get(repayment.first_repay_day)
    if installment_info[0]:
        min_id = installment_info[0]['installment_number']
    for info in installment_info:
        i = info["installment_number"]
        installments = InstallmentDetailInfo.objects.filter(Q(repayment=repayment) & Q(installment_number = i))
        should_repay_time = first_repay_day.replace(months=i).naive
        if not installments.first():
            detail = InstallmentDetailInfo(
                repayment=repayment,
                installment_number=i,
                should_repay_time=should_repay_time,
                real_repay_time=None,
                should_repay_amount=trans_to_cent(info['should_pay_amount']),
                ori_should_repay_amount=trans_to_cent(info['should_pay_amount']),
                repay_principle=0,
                repay_interest=0,
                repay_fee=0,
                real_repay_amount=0,
                repay_status=RepaymentInfo.OVERDUE,
                repay_channel=0,
                repay_overdue=0,
                reduction_amount=0,
                repay_overdue_interest=0,
                repay_penalty=0,
                repay_bank_fee=0,
                overdue_days=0,
                order_number = '0',
            )
            detail.save()
            installment = detail
        else:
            installment = installments[0]

        installment.order_number = info["installment_id"]
        installment.should_repay_amount = trans_to_cent(info["should_pay_amount"])
        installment.overdue_days = get_days(info["overdue_days"])
        installment.repay_overdue = trans_to_cent(info["overdue_amount"])
        installment.update_at = datetime.now()
        if int(info["overdue_days"]) > 0:
            installment.repay_status = RepaymentInfo.OVERDUE
        installment.save()

        max_id = i
        max_overdue_days = max(max_overdue_days, int(info["overdue_days"]))
        rest_repay_money += trans_to_cent(info['should_pay_amount'])
        ori_collection_amount += trans_to_cent(info['should_pay_amount'])

    #???
    collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(type__in=["", "b", "c", "d", "e", 'g'a, 'h']) & Q(status__in=['0', 'i', 'ci', 'd', 's1', 's2', 's3'])).order_by('-id')
    collection_type = get_collection_type(max_overdue_days)

    print 'collection_apply'
    print collection_apply
    if collection_apply:

        # money 不更新, 只在创建 apply 时 初始化.
        # collection_apply.update(overdue_days=max_overdue_days, money=min_id -1)
        collection_apply.update(overdue_days=max_overdue_days)

    if not (not collection_apply.first()
        or collection_apply.first().status in [Apply.REPAY_SUCCESS, Apply.COLLECTION_SUCCESS, Apply.RENEW]):
        # status = collection_apply.first().status
        # if int(i - 1) > int(collection_apply.first().money):
        # if (collection_apply.status in [Apply.REPAY_SUCCESS, Apply.COLLECTION_SUCCESS]) or collection_type != collection_apply.first().type:
        # if (collection_apply.first().status in [Apply.REPAY_SUCCESS, Apply.COLLECTION_SUCCESS]) or collection_type > collection_apply.first().type:
        if collection_type > collection_apply.first().type:
            # 类型(m1, m2, ...)的变化
            status = Apply.WAIT
            print "new status"
            print status
            print type(status)
            create_at = datetime.now()

            # collection_apply.update(type=collection_type, money=min_id - 1, status=status)
            # print 'next status: %s' % collection_apply.first().id
            report_data_collection_money(collection_apply.first(), u"已流转")


            collection_apply.update(
                type=collection_type, status=status, create_at=create_at, update_at=create_at,
                overdue_days=max_overdue_days, rest_repay_money=rest_repay_money, platform=org_account)

            report_data_collection_money(collection_apply.first())
        # else:
            # collection_apply.update(type=collection_type, money=i - 1)
    else:
        print "new apply"
        collection_apply = Apply(
            create_by=repayment.user, money=min_id -1, repayment=repayment, status=Apply.WAIT,
            type=collection_type, update_at=datetime.now(), create_at=datetime.now(), overdue_days=max_overdue_days,
            rest_repay_money=rest_repay_money, ori_collection_amount=ori_collection_amount, platform=org_account)
        collection_apply.save()

        report_data_collection_money(collection_apply)

    print 'out gen_installs_info'


def gen_repayment_info(data, u, c, org_account):
    repay_info = data["repayment_info"]
    try:
        ensure_repayment_info_has_key(repay_info)
        #check_none(repay_info)
        #repay_next_id = RepaymentInfo.objects.all().order_by("-id")[0].id + 1
        #repay_info["id"] = repay_next_id
        #这里默认就是5了
        repay_info["repay_status"] = RepaymentInfo.PAYED
        #if not repay_info.has_key('order_number') or repay_info['order_number'] == "":
        #    repay_info['order_number'] = repay_info['repayment_id']
        #print RepaymentInfo.objects.filter(order_number = data["repayment_info"]["order_number"])
        #print "$$$", data["repayment_info"]["order_number"]
        #这里用一个大的数 表示channel 前缀   这里的import_id = channel 前缀 + 第三方的自己的id
        #print 3
        rr = RepaymentInfo.objects.filter(order_number = repay_info["repayment_id"])
        r = None
        if (rr.count() >0):
            r = rr[0]
        else:
            r = RepaymentInfo()
        r.platform = org_account
        r.order_number = repay_info["repayment_id"]
        r.repay_status = RepaymentInfo.OVERDUE
        r.apply_amount = trans_to_cent(repay_info["amount"])
        r.exact_amount = trans_to_cent(repay_info["amount"])
        r.repay_amount = trans_to_cent(repay_info["repay_amount"])
        r.rest_amount = trans_to_cent(repay_info["rest_amount"])
        r.user = u
        # r.strategy_id = repay_info["installment_count"]
        r.installment_count = repay_info["installment_count"]
        r.strategy_id = 1

        r.bank_card = c
        r.apply_time = get_date(repay_info["apply_time"])
        r.first_repay_day = get_date(repay_info["pay_time"])
        r.reason = ""
        #r.next_repay_time =
        #r.last_time_repay =

        r.overdue_days = max(int(ii["overdue_days"]) for ii in repay_info["installment_info"])


        print "repay_info", r.repay_amount, repay_info["repay_amount"]
        r.save()
        if repay_info['installment_count'] != InstallmentDetailInfo.objects.filter(repayment=r).count():
            if InstallmentDetailInfo.objects.filter(repayment=r).exclude(repay_status__in=[2, 8]).count() > 0:
                # print InstallmentDetailInfo.objects.filter(Q(repayment=r) & ~Q(repay_status__in=[7, 8]))
                cmp_status = "greater than"
                if repay_info['installment_count'] > InstallmentDetailInfo.objects.filter(repayment=r).count():
                    cmp_status = "less than"
                print "%s repayment %s installment count: %s != count(installment): %s" % (cmp_status, r, repay_info['installment_count'], InstallmentDetailInfo.objects.filter(repayment=r).count())
        installment_info = repay_info["installment_info"]
        gen_installs_info(r, installment_info, org_account)
    except ImportError, e:
        raise e
    except Exception , e:
        traceback.print_exc()
        print "ecp", e
        raise ImportError(ImportError.EC_DB, "save repayment info failed %s" % str(e))

# #@csrf_exempt
# def update_collection_status(info):
    # user_info = info["user_info"]
    # repayment_info = info["repayment_info"]

    # users = User.objects.filter(Q(phone_no = user_info['phone_no']))
    # if (users.count() > 1):
        # raise ImportError(ImportError.EC_DUP, "%s多个重复用户" % ( user_info['phone_no']))
    # elif users.count() == 1:
        # u = users[0]
    # else:
        # raise ImportError(ImportError.EC_DUP, "%s用户不存在" % ( user_info['phone_no']))


    # # 获取repayment
    # # installment = InstallmentDetailInfo.objects.filter(id=repayment_info['repayment_id']).first()
    # # if not installment:
        # # raise ImportError(ImportError.EC_LACK, "未找到该installment_id %s:%s" % (u.name, repayment_info["repayment_id"]))
    # repayments = RepaymentInfo.objects.filter(Q(user = u) & Q(order_number = repayment_info["repayment_id"]))
    # # repayments = RepaymentInfo.objects.filter(Q(user = u) & Q(id=installment.repayment.id))
    # if len(repayments) != 1:
        # raise ImportError(ImportError.EC_LACK, "未找到该repayment_id %s:%s" % (u.name, repayment_info["repayment_id"]))
    # repayment = repayments[0]

    # # 还清所有当前状态逾期的installment
    # installments = InstallmentDetailInfo.objects.filter(Q(repayment=repayment) & Q(repay_status=RepaymentInfo.OVERDUE))
    # for installment in installments:
        # installment.repay_status = RepaymentInfo.OVERDUE_DONE
        # installment.save()

    # # collection_applys = Apply.objects.filter(Q(repayment = repayment) & Q(type=Apply.COLLECTION_M1) & Q(status = Apply.WAIT))
    # collection_applys = Apply.objects.filter(Q(repayment = repayment) & Q(status__in=[Apply.WAIT, "i", "ci"]) & Q(type__in=["b", "c", "d", "e"]))
    # for collection_apply in collection_applys:
        # collection_apply.status = Apply.REPAY_SUCCESS
        # collection_apply.save()

        # report_data_collection_money(collection_apply)

    # # 更新repayment状态
    # print "repayment"
    # print repayment
    # repayment.repay_status= RepaymentInfo.OVERDUE_DONE
    # repayment.save()


def get_dingdang_repayment_overdue_data(data):
    """获取叮当: 逾期天数, 对应催收类型, 最早一期的工单号"""
    print 'in get_dingdang_repayment_overdue_data'
    overdue_days = max([ins_data['overdue_days'] for ins_data in data])
    overdue_type = get_collection_type(overdue_days)
    order_number_dic = {ins_data['installment_number']: ins_data['installment_id'] for ins_data in data}
    ins_order_number = order_number_dic[max(order_number_dic.keys())]
    should_repay_amount = int(sum([ins_data['should_pay_amount'] for ins_data in data]) * 100.0)

    data = dict(
        installment_order_number=ins_order_number,
        should_repay_amount=should_repay_amount,
        overdue_type=overdue_type,
        overdue_days=overdue_days,
        latest_installment_count=len(data),
    )
    print data
    print 'out get_dingdang_repayment_overdue_data'
    return data

def get_dingdang_repayment_type(repayment, overdue_type, ins_order_number):
    """贷款记录type: 委案 or 更新

    委案:
        没有对应的 repayment_record
        overdue_type 不相等(催收类型改变了)
        installment_order_number 不相等(最近一期工单号不相等时)
    """
    ins_order_number = str(ins_order_number)
    if not repayment:
        return 0
    print repayment.overdue_type, overdue_type
    print repayment.overdue_type != overdue_type
    print repayment.installment_order_number, ins_order_number
    print repayment.installment_order_number != ins_order_number
    if repayment.overdue_type != overdue_type or repayment.installment_order_number != ins_order_number:
        return 0

    return 1


def dingdang_repayment_record(data):
    """叮当进件数据

    催收状态改变时: 新建一条 委案记录.
    催收状态未改变: 新建一条 更新记录, 后续相同的催收状态的数据,直接更新这条记录.
    """
    try:
        print "in dingdang_repayment_record"
        print '*********************************'

        repayment_info = data['repayment_info']
        overdue_dic = get_dingdang_repayment_overdue_data(repayment_info['installment_info'])

        repayment = RepaymentInfo.objects.filter(order_number=repayment_info['repayment_id']).first()
        installment = InstallmentDetailInfo.objects.filter(order_number=overdue_dic['installment_order_number']).first()
        installment_number = installment.installment_number

        collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__lte=installment_number - 1) & Q(type__in=["b", "c", "d", "e", 'g', 'h'])).order_by("-id").first()
        # apply 肯定有
        if not collection_apply:
            collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__gte=installment_number - 1) & Q(type__in=["b", "c", "d", "e", 'g', 'h'])).order_by("id").first()
        apply = collection_apply
        # apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__gte=installment.installment_number - 1) & Q(type__in=["b", "c", "d", "e", 'g', 'h'])).order_by("id").first()
        collect_record = CollectionRecord.objects.filter(apply=apply, record_type=CollectionRecord.DISPATCH).order_by("-id").first()
        collector = None
        if collect_record:
            collector = collect_record.create_by
        print "apply: %s, collector: %s" % (apply, collector)

        repayment_record = DingdangRepaymentRecord.objects.filter(order_number=repayment_info['repayment_id']).order_by('-id').first()
        type = get_dingdang_repayment_type(repayment_record, overdue_dic['overdue_type'], overdue_dic['installment_order_number'])
        print 'repayment type: %s' % type
        strategy_id = data['strategy_id']
        other_dic = dict(
            apply=apply,
            collector=collector,
            type=type,
            strategy_id=strategy_id,
        )

        repayment_dic = dict(
            order_number=repayment_info['repayment_id'],
            installment_count=repayment_info['installment_count'],

            apply_amount=repayment_info['amount'],
            exact_amount=repayment_info['amount'],
            real_repay_amount=int(float(repayment_info['repay_amount']) * 100.0),
            rest_amount=int(float(repayment_info['rest_amount']) * 100.0),

            apply_time=repayment_info['apply_time'],
        )
        user_info = data['user_info']
        user_dic = dict(
            user_name=user_info['name'],
            id_no=user_info['id_no'],
            phone_no=user_info['phone_no'],
            channel=user_info['channel'],
        )

        bank_info= data['card_info']
        bank_dic = dict(
            bank_card_number=bank_info['card_number'],
            bank_card_name=bank_info['bank_type'],
        )
        update_data = {}
        update_data.update(bank_dic)
        update_data.update(user_dic)
        update_data.update(overdue_dic)
        update_data.update(other_dic)
        update_data.update(repayment_dic)

        print update_data
        if type == 0:
            repayment_record = DingdangRepaymentRecord(**update_data)
            repayment_record.save()
        else:
            repayment_record = DingdangRepaymentRecord.objects.filter(order_number=repayment_info['repayment_id'], installment_order_number=overdue_dic['installment_order_number'], type=1).order_by('-id')
            if not repayment_record:
                repayment_record = DingdangRepaymentRecord(**update_data)
                repayment_record.save()
            else:
                update_data['update_at'] = datetime.now()
                repayment_record.update(**update_data)

        # print repayment_record.id
        print '&&&&&&&&&&&&'
        print "out dingdang_repayment_record"

    except Exception as e:
        print e
        return -1


def dingdang_repay_record_all(datas):
    print "in dingdang_repay_record_all"
    try:
        for data in datas:
            dingdang_repay_record(data)

    except Exception as e:
        print e
        return -1


def dingdang_repay_record(info):
    """叮当回款信息 记录表

    查询条件:
    """
    print "in dingdang_repay_record"
    try:
        print info['user_info']['name']
        repayment_info = info["repayment_info"]
        real_repay_amount = int(repayment_info['amount'] * 100.0)
        real_repay_time = repayment_info['pay_time']
        repayment_order_number = repayment_info['repayment_id']
        installment_order_number = repayment_info['installment_id']
        apply_time = repayment_info['apply_time']

        repayment = RepaymentInfo.objects.filter(order_number=repayment_order_number).first()
        installment = InstallmentDetailInfo.objects.filter(order_number=installment_order_number).first()
        installment_number = installment.installment_number

        # collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(status__in=[Apply.WAIT, "i", "ci", "d"]) & Q(type__in=["b", "c", "d", "e"])).first()
        collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__lte=installment_number - 1) & Q(type__in=["b", "c", "d", "e", 'g', 'h'])).order_by("-id").first()
        # apply 肯定有
        if not collection_apply:
            collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__gte=installment_number - 1) & Q(type__in=["b", "c", "d", "e", 'g', 'h'])).order_by("id").first()
        apply = collection_apply
        collect_record = CollectionRecord.objects.filter(apply=apply, record_type=CollectionRecord.DISPATCH).order_by("-id").first()
        collector = None
        print "installment_number"
        print installment_number
        print "apply"
        print apply
        print repayment
        print "collect_record"
        print collect_record
        if collect_record:
            collector = collect_record.create_by

        update_data = dict(
            real_repay_amount=real_repay_amount,
            real_repay_time=real_repay_time,
            repayment_order_number=repayment_order_number,
            installment_order_number=installment_order_number,
            apply_time=apply_time,
            apply=apply,
            collector=collector,
        )
        q = dict(
            collector=collector,
            apply=apply,
            installment_order_number=installment_order_number,
        )
        repay_record = DingdangRepayRecord.objects.filter(**q)
        print 'repay_record'
        print repay_record

        if repay_record:
            update_data['update_at'] = datetime.now()
            repay_record.update(**update_data)
        else:
            repay_record = DingdangRepayRecord(**update_data)
            repay_record.save()

        print "out dingdang_repay_record"
        return repay_record

    except Exception as e:
        print e
        return -1

def update_collection_status_new(info):
    print 'in update_collection_status_new'
    user_info = info["user_info"]
    repayment_info = info["repayment_info"]

    # dingdang_repay_record(info)

    users = User.objects.filter(Q(phone_no = user_info['phone_no']))
    #if (users.count() > 1):
    #    raise ImportError(ImportError.EC_DUP, "%s多个重复用户" % ( user_info['phone_no']))
    #elif users.count() == 1:
    #    u = users[0]

    if not users:
        raise ImportError(ImportError.EC_DUP, "%s用户不存在" % ( user_info['phone_no']))


    # 获取repayment
    installment = InstallmentDetailInfo.objects.filter(order_number=repayment_info['installment_id']).first()
    repayment = installment.repayment
    overdue_installments = InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[2])
    overdue_installments_order_number = [oi.order_number for oi in overdue_installments]
    print 'overdue_installments_order_number'
    print overdue_installments_order_number

    if not installment:
        raise ImportError(ImportError.EC_LACK, "未找到该installment_id %s" % repayment_info["repayment_id"])

    # 还清所有当前状态逾期的installment
    installment.repay_status = RepaymentInfo.OVERDUE_DONE
    installment.real_repay_time = repayment_info.get("pay_time")
    installment.real_repay_amount = int(repayment_info.get("amount") * 100)
    installment.save()

    if str(repayment_info['installment_id']) not in overdue_installments_order_number:
        print 'already repay update_collection_status_new'
        # return 1

    # repayment = RepaymentInfo.objects.filter(id=installment.repayment.id).first()
    overdue_installments = InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status=2)
    print 'overdue installments'
    print overdue_installments
    #???
    # collection_applys = Apply.objects.filter(Q(repayment = repayment) & Q(type=Apply.COLLECTION_M1) & Q(status = Apply.WAIT))
    collection_applys = Apply.objects.filter(Q(repayment = repayment) & Q(status__in=[Apply.WAIT, "i", "ci", "d", 's1', 's2', 's3']) & Q(type__in=["b", "c", "d", "e", 'g', 'h'])).order_by('-id').first()
    if not collection_applys:
        print 'dont have collection_applys'
        return 1

    if not overdue_installments:
        # collection_applys = Apply.objects.filter(Q(repayment = repayment) & Q(status__in=[Apply.WAIT, "i", "ci"]) & Q(type__in=["b", "c", "d", "e"]))
        print "collection_applys"
        print collection_applys
        for collection_apply in [collection_applys]:
            collection_apply.status = Apply.REPAY_SUCCESS
            collection_apply.real_repay_time = repayment_info.get("pay_time")
            # collection_apply.rest_repay_money = int(repayment_info.get("amount") * 100)
            collection_apply.save()

            # report_data_collection_money(collection_apply)
            # collection_apply.update_at = datetime.now()
            # collection_apply.save()

        # 更新repayment状态
        print "repayment"
        print repayment
        repayment.repay_status= RepaymentInfo.OVERDUE_DONE
        repayment.save()
    else:
        for collection_apply in [collection_applys]:
            collection_apply.status = Apply.PARTIAL_SUCCESS
            collection_apply.real_repay_time = repayment_info.get("pay_time")
            # collection_apply.rest_repay_money = int(repayment_info.get("amount") * 100)
            collection_apply.save()

    print 'out update_collection_status_new'

def report_data_repay(datas):
    """上报 部分成功, 成功 数据"""
    print "in report_data_repay\n"
    try:
        apply_dic = {}
        for data in datas:
            try:
                repayment_info_dic = data["repayment_info"]
                ins_order_number = repayment_info_dic["installment_id"]
                repayment = InstallmentDetailInfo.objects.filter(order_number=ins_order_number).first().repayment
                repayment_order_number = repayment.order_number
                print repayment
                # apply = Apply.objects.filter(Q(repayment = repayment) & Q(status__in=["d", "8", "9"]) & Q(type__in=["b", "c", "d", "e"])).first()
                # apply = Apply.objects.filter(Q(repayment = repayment) & Q(status__in=[Apply.WAIT, "i", "ci", "d", "8", "9"]) & Q(type__in=["b", "c", "d", "e"])).first()
                installment_number = InstallmentDetailInfo.objects.filter(order_number=ins_order_number).first().installment_number
                apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__lte=installment_number - 1) & Q(type__in=["a", "b", "c", "d", "e", 'g', 'h'])).order_by("-id").first()
                money = repayment_info_dic["amount"] * 1.0
                repay_time = repayment_info_dic['pay_time']
                print repayment
                print apply
                print
                # apply: 是肯定有的.
                # 之前有一部份数据, money 是 installment_number 最小值.
                if not apply:
                    apply = Apply.objects.filter(Q(repayment = repayment) & Q(money__gte=installment_number - 1) & Q(type__in=["a", "b", "c", "d", "e", 'g', 'h'])).order_by("id").first()

                if apply:
                    print apply_dic.get(repayment_order_number)
                    pre_money = apply_dic.get(repayment_order_number)[1] if apply_dic.get(repayment_order_number) else 0
                    ins_order_numbers = apply_dic.get(repayment_order_number)[2] if apply_dic.get(repayment_order_number) else []
                    ins_order_numbers.append(ins_order_number)
                    print "ins_order_numbers"
                    print ins_order_numbers
                    apply_dic[repayment_order_number] = [apply, pre_money + money, ins_order_numbers, repay_time]
                    print apply_dic
            except Exception as e:
                print "in report_data_repay data error"
                print e

        for repayment_order_number, (apply, money, ins_order_numbers, repay_time) in apply_dic.items():
            try:
                print apply
                print ins_order_numbers
                rest_repay_money = int(money * 100.0)
                print "%s: %s" % ( rest_repay_money, sum([drd.real_repay_amount for drd in DingdangRepayRecord.objects.filter(installment_order_number__in=ins_order_numbers)]))
                if rest_repay_money != sum([drd.real_repay_amount for drd in DingdangRepayRecord.objects.filter(installment_order_number__in=ins_order_numbers)]):
                    report_data_collection_money(apply, rest_repay_money=money, recover_date=datetime.strptime(repay_time, '%Y-%m-%d'))

                if apply.status in [Apply.REPAY_SUCCESS]:
                    apply.rest_repay_money = rest_repay_money
                    apply.real_repay_money = rest_repay_money
                else:
                    # 部分回款
                    # apply.rest_repay_money = apply.rest_repay_money - rest_repay_money
                    installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status=2)
                    apply.rest_repay_money = sum([ins.should_repay_amount for ins in installments])
                    apply.real_repay_money = rest_repay_money

                apply.update_at = datetime.now()
                apply.save()

            except Exception as e:
                print "in report_data_repay update apply error"
                print e

        print "out report_data_repay"
    except Exception as e:
        print "report_data_repay error:"
        print e



@csrf_exempt
@require_http_methods(["POST"])
def update_collection_info(request):
    if request.method == 'POST':
        ret_json = {}
        error_list = []
        #Log().warn("update_collection_info: %s" % request.body)
        #print request.body
        try:
            try:
                req = json.loads(request.body)
            except Exception , e:
                send_mail("update_collection_info request body error", str(request.body))
                raise ImportError(ImportError.EC_JSON, "")

            org_account = req.get('org_account')
            org_token = req.get('org_token')
            verify_id(org_account, org_token)

            fail_num = 0
            for data in req["actual_collection_data"]:
                try:
                    update_collection_status_new(data)
                except ImportError, e:
                    print 'update_collection_info in data import error'
                    fail_num += 1
                    error_list.append(e.get_error("%s" % data))
                except Exception, e:
                    print 'update_collection_info in data other error'
                    print e
                    fail_num += 1
                    error_list.append("%s, data: %s" % (e, data))

            report_data_repay(req["actual_collection_data"])
            # 回款,金额相同, installment_order_number 相同时 不上报, 所以在后面保存记录(通常应该在最前).
            dingdang_repay_record_all(req["actual_collection_data"])

            all_num = len(req['actual_collection_data'])
            success_num = all_num - fail_num
            ret_json['success_num'] = success_num
            ret_json['fail_num'] = fail_num
            ret_json["error_list"] = error_list
            msg ='update_collection_info: total_count:{0} success_num: {1}'.format(all_num, success_num)
            Log().info('update_collection_info: total_count:{0} success_num: {1}'.format(all_num, success_num))

            if fail_num > 0:
                send_mail("update_collection_info error", "%s\n%s" % (msg, json.dumps(ret_json)))
            # yagmail.register('dengzhehao@rongshutong.com', '123mint!')
            # mail_client = yagmail.SMTP()
            # content = 'update_collection_info: total_count:{0} success_num: {1}'.format(all_num, success_num)
            # mail_client.send("dengzhehao@rongshutong.com", "subject", content)

        except ImportError, e:
            print "endi,", e
            traceback.print_exc()
            send_mail("update_collection_info import error", str(e))
            return e.get_response()
        except Exception, e:
            print "ende,", e
            print e
            send_mail("update_collection_info other error", str(e))
            traceback.print_exc()
            return HttpResponse(json.dumps({"success":False, "error_msg":str(e), "error":"内部服务错误"},ensure_ascii=False))
    print ret_json
    return HttpResponse(json.dumps(ret_json,ensure_ascii=False))


def verify_id(org_account, org_token):
    """验证 第三方平台"""
    dic = {
        'platform': 'yijiejing',
        'token': 'yijiejing201612',
    }
    if org_account == dic['platform'] and org_token == dic['token']:
        msg = u''
        return 0
    msg = 'account 或者 token 不正确.'
    raise ValueError(msg)



@csrf_exempt
@require_http_methods(["POST"])
def import_collection_info(request):
    ret_json = {}
    if request.method == 'POST':
        error_list = []
        try:
            try:
                req = json.loads(request.body)
            except Exception , e:
                send_mail("import_collection_info request body error", str(request.body))
                raise ImportError(ImportError.EC_JSON, "")
            #if req["all_collection_data_length"] != str(len(req["actual_collection_data"])):
            #    error["error_msg"] = u"数据长度不一致"
            #    error["error_code" ] = "100001"
            #    error_list.append(error)
            #    ret_json["error_list"] = error_list
            #    return HttpResponse(json.dumps(ret_json,ensure_ascii=False))


            fail_num = 0
            start_time = time.time()

            org_account = req.get('org_account')
            org_token = req.get('org_token')
            verify_id(org_account, org_token)

            org_account = 'rst'

            for data in req["actual_collection_data"]:
                try:
                    print '--------\n\n'
                    user_data = trans_to_inner_field(data)
                    user_data['string_platform'] = org_account

                    result = user_center_client.import_user_data(**user_data)
                    print user_data
                    print result
                    print '\n\n'
                    user = User.objects.get(id=result.user_id)
                    q_bank_card = {
                        "card_number": data["card_info"]["card_number"],
                        "owner": user,
                    }
                    bank_card = BankCard.objects.filter(**q_bank_card).first()
                    gen_repayment_info(data, user, bank_card, org_account)
                    print "repayment generate success"

                    # u = gen_user_and_contacts(data, org_account)
                    # if u != None:
                        # print "user generate success"
                        # c = gen_card_info(data, u)
                        # if c != None:
                            # print "card generate success"
                            # gen_repayment_info(data, u, c, org_account)
                            # print "repayment generate success"
                except ImportError, e:
                    print 'import_collection_info in data import error'
                    fail_num += 1
                    error = e.get_error("%s data:%s" % (data["user_info"]["name"], data))
                    error_list.append(error)
                except Exception, e:
                    print 'import_collection_info in data other error'
                    print e
                    fail_num += 1
                    error_list.append("%s, data: %s" % (e, data))

                # 新建一个进件记录
                dingdang_repayment_record(data)

            end_time = time.time()
            all_num = len(req['actual_collection_data'])
            success_num = all_num - fail_num
            ret_json['success_num'] = success_num
            ret_json['fail_num'] = fail_num
            ret_json["error_list"] = error_list
            print 'import_collection_info: total_count:{0} success_num: {1} spend_time:{2}'.format(all_num, success_num, end_time - start_time)
            msg = 'import_collection_info: total_count:{0} success_num: {1} spend_time:{2}'.format(all_num, success_num, end_time - start_time)
            Log().info(msg)

            if fail_num > 0:
                send_mail("import_collection_info error", "%s\n%s" % (msg, json.dumps(ret_json,ensure_ascii=False)))

            #默认成功返回
        except ImportError, e:
            print "endi,", e
            traceback.print_exc()
            send_mail("import_collection_info import error", str(e))
            return e.get_response()
        except Exception, e:
            #print "ende,", e
            print e
            traceback.print_exc()
            send_mail("import_collection_info other error", str(e))
            return HttpResponse(json.dumps({"success":False, "error_msg":str(e), "error":"内部服务错误"},ensure_ascii=False))
    #print ret_json
    #Log().warn("resp: %s" % ret_json)
    return HttpResponse(json.dumps(ret_json,ensure_ascii=False))

def get_json_from_repayment_list(order_number_list):

    json_data = {}
    #json_data["all_collection_data_length"] = str(len(order_number_list))
    json_data["channel"] = 100000 # 100000 代表玖富
    actual_collection_data= []
    for i in order_number_list:
        actual_collection_data.append(get_json_from_repayment(i))
    json_data["actual_collection_data"] = actual_collection_data
    #print json.dumps(json_data)
    return json.dumps(json_data,ensure_ascii=False)

def get_json_from_repayment(repayment_order_number):
    r = RepaymentInfo.objects.filter(order_number = repayment_order_number)[0]
    u = r.user
    repayment_info = {}
    #repayment_info["id"] = str(r.id)
    repayment_info["apply_amount"] = str(r.apply_amount)
    repayment_info["first_repay_day"] = str(r.first_repay_day)
    repayment_info["repay_status"] = '1'
    repayment_info["strategy_id"] = "15"
    #repayment_info["bank_card_id"] = "1331"
    repayment_info["import_id"] =  2342455
    #repayment_info["order_number"] = ""
    card_info = {}
    card_info['card_number'] = "24322434233333"
    card_info['bank_type'] = "1"
    card_info['card_type'] = "2"
    user_info = {}
    #user_info["id_no"] = ""
    #user_info["id_no"] = None
    user_info["id_no"] = "430524198606144856"
    #user_info["id_no"] = str(u.id_no)
    user_info["phone_no"] = str(u.phone_no)
    user_info["name"] = "xiaojun"
    #user_info["name"] = str(u.name)
    info = {}
    info["card_info"] = card_info
    info["user_info"] = user_info
    info["repayment_info"] = repayment_info
    #info["channel"] = 100000 # 100000 代表玖富
    #info["strategy_id"] = "11"
    contact_list = []
    list_data = ContactInfo.objects.filter(owner = u)
    for item in list_data:
        i = {}
        for field in ContactInfo._meta.get_all_field_names():
            if field in ["name","phone_no","relationship"]:
                i[field] = str(getattr(item, field, None))
        contact_list.append(i)
    info["contact_list"] = contact_list
    actual_collection_data = []
    info["user_info"] = user_info
    info["repayment_info"] = repayment_info
    return info

@csrf_exempt
def generate_collection_info(request):
    if request.method == 'GET':
        try:
            ret_json = get_json_from_repayment_list(["7614447080240011461"])
            #ret_json = get_json_from_repayment_list(["7614447080240011461","2830769681751742887"])
            try:
                httpClient = httplib.HTTPConnection("114.55.33.62", 8899, timeout=30)
                headers = {"Content-type": "application/json"}
                httpClient.request("POST", "/collection/import_collection_info", ret_json.encode('utf-8'), headers)
                response = httpClient.getresponse()
                resp = response.read()
                #print resp
            except Exception, e:
                print e
            finally:
                if httpClient:
                    httpClient.close()
        except Exception, e:
            print e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"内部服务错误"}))
    return HttpResponse(resp)

def submit_data_server(data):
    try:
        data = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        req = urllib2.Request(url = settings.DATA_SERVER['SUBMIT_URL'], headers = headers)
        rsp = urllib2.urlopen(req, data = data).read()
        rsp = json.loads(rsp)
        if rsp['err_code'] != 0:
            Log().error('submit_data_server failed, rsp:{0}'.format(rsp))
            raise ImportError(ImportError.EC_INTERNAL, 'to data_server failed: {0}'.format(rsp['err_code']))
    except Exception,e:
        traceback.print_exc()
        raise ImportError(ImportError.EC_INTERNAL, 'to data_server failed: {0}'.format(e))

def save_user_addressbook(data):
    try:
        u = None
        users = User.objects.filter(Q(channel = data['channel']) & Q(phone_no = data['phone_no']))
        if users.count() > 1:
            raise ImportError(ImportError.EC_DUP, "%s,%s多个重复用户" % (data['channel'], data['phone_no']))
        elif users.count() == 1:
            u = users[0]
        else:
            raise ImportError(ImportError.EC_NULL, "%s,%s用户不存在" % (data['channel'], data['phone_no']))
        save_data = {'org_account': settings.DATA_SERVER['ORG_NAME'],
                     'service_id': settings.DATA_SERVER['SERVICE_ID'],
                     'user_info': {'user_id': u.id,
                                   'name': u.name,
                                   'id_card_num': u.id_no,
                                   'phone_num': u.phone_no,
                                   'address_book': data['addressbook']}}
        submit_data_server(save_data)
    except ImportError, e:
        raise e
    except Exception,e:
        traceback.print_exc()
        raise ImportError(ImportError.EC_INTERNAL, str(e))

def save_user_callrecords(data):
    try:
        u = None
        users = User.objects.filter(Q(channel = data['channel']) & Q(phone_no = data['phone_no']))
        if users.count() > 1:
            raise ImportError(ImportError.EC_DUP, "%s,%s多个重复用户" % (data['channel'], data['phone_no']))
        elif users.count() == 1:
            u = users[0]
        else:
            raise ImportError(ImportError.EC_NULL, "%s,%s用户不存在" % (data['channel'], data['phone_no']))
        save_data = {'org_account': settings.DATA_SERVER['ORG_NAME'],
                     'service_id': settings.DATA_SERVER['SERVICE_ID'],
                     'user_info': {'user_id': u.id,
                                   'name': u.name,
                                   'id_card_num': u.id_no,
                                   'phone_num': u.phone_no,
                                   'phone_call': data['call_records']}}
        submit_data_server(save_data)
    except ImportError, e:
        raise e
    except Exception,e:
        traceback.print_exc()
        raise ImportError(ImportError.EC_INTERNAL, str(e))


@csrf_exempt
def import_addressbook_info(request):
    if request.method == 'POST':
        ret_json = {}
        error_list = []
        Log().warn('req: {0}'.format(request.body))
        print '1 try'
        try:
            print '2 try'
            try:
                req = json.loads(request.body)
            except Exception,e:
                raise ImportError(ImportError.EC_JSON, "")
            fail_num = 0
            print '3 try'
            for data in req['actual_addressbook_data']:
                try:
                    save_user_addressbook(data)
                except Exception,e:
                    fail_num += 1
                    error = e.get_error(data['phone_no'])
                    error_list.append(error)
            print 'out try'
            all_num = len(req['actual_addressbook_data'])
            success_num = all_num - fail_num
            ret_json['success_num'] = success_num
            ret_json['fail_num'] = fail_num
            ret_json['error_list'] = error_list
        except ImportError,e:
            traceback.print_exc()
            return e.get_response()
        except Exception,e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"success":False, "error_msg":str(e), "error":"内部服务错误"},ensure_ascii=False))
        Log().warn('resp: {0}'.format(ret_json))
        return HttpResponse(json.dumps(ret_json, ensure_ascii = False))

@csrf_exempt
def import_callrecords_info(request):
    if request.method == 'POST':
        ret_json = {}
        error_list = []
        Log().warn('req: {0}'.format(request.body))
        print '1 try'
        try:
            print '2 try'
            try:
                req = json.loads(request.body)
            except Exception,e:
                raise ImportError(ImportError.EC_JSON, "")
            fail_num = 0
            print '3 try'
            for data in req['actual_callrecords_data']:
                try:
                    save_user_callrecords(data)
                except Exception,e:
                    fail_num += 1
                    error = e.get_error(data['phone_no'])
                    error_list.append(error)
            all_num = len(req['actual_callrecords_data'])
            success_num = all_num - fail_num
            ret_json['success_num'] = success_num
            ret_json['fail_num'] = fail_num
            ret_json['error_list'] = error_list
        except ImportError,e:
            traceback.print_exc()
            return e.get_response()
        return HttpResponse(json.dumps(ret_json, ensure_ascii = False))

