# -*- coding:utf-8 -*-
import time

import re
from datetime import datetime, date
import copy
import requests

from openpyxl.utils.datetime import from_excel

from django.core.cache import cache
from django.conf import settings
from business_manager.util.import_file_util import ImportFile
from business_manager.import_data.models import (
    ParseFileRecord, UploadFile, ImportModule, ImportField
)
from business_manager.import_data.services import repayment_create_or_update, contact_create_or_update
from business_manager.util.import_file_util import ImportFileException
from business_manager.user_center.user_center_client import UserCenterClient
from business_manager.collection.models import InstallmentDetailInfo, RepaymentInfo
from business_manager.order.apply_models import Apply, InfoField, InfoModule
from business_manager.review.models import CollectionRecord
from business_manager.collection.report import report_collection
from business_manager.order.models import User, BankCard


client = UserCenterClient(settings.USER_CENTER_SERVER['HOST'], settings.USER_CENTER_SERVER['PORT'], 2000)

REDIS_KEY_TEMPLATE = "parse_record_{}"
VALUE_TEMPLATE = "t{total_count}_s{success_count}_f{fail_count}"


def parse_file(parse_record_id, platform):
    print 'in parse_file'
    # update parse file record status
    record = ParseFileRecord.objects.filter(id=parse_record_id).first()
    file_obj = record.file.upload_file
    try:
        import_file = ImportFile(file_obj)
        sheet_content = import_file.process_content(record.id)
    except ImportFileException as e:
        print("get sheet content error: %s" % e.msg)
        record.status = ParseFileRecord.PARSED_FAILED
        record.save()
        import_module = ImportModule.objects.filter(id=record.module.id).first()
        if import_module:
            import_module.status = 0
            import_module.save()

        return
    except Exception as e:
        print("get sheet content failed: %s" % e)
        record.status = ParseFileRecord.PARSED_FAILED
        record.save()

        import_module = ImportModule.objects.filter(id=record.module.id).first()
        if import_module:
            import_module.status = 0
            import_module.save()
        return
    total_count = len(sheet_content)
    print sheet_content
    print("total_count ", total_count)
    record.status = ParseFileRecord.PARSING
    record.total_count = total_count
    record.save()

    delete_redis_key(parse_record_id)
    save_to_redis(parse_record_id, total_count)
    fail_data = []
    if record.module.module_type == ImportModule.REPAIR_MSG:
        info_repair = InfoRepairImport(record.id, record.creator)
        fail_data = info_repair.save_repair_msg(sheet_content, platform, record.module.id)
    elif record.module.module_type == ImportModule.IMPORT_CONTACT:
        latest_data = {}
        for data in sheet_content:
            fail = copy.deepcopy(data)

            data.update(latest_data)
            latest_data = data
            try:
                ret = contact_create_or_update([data])
            except KeyError as e:
                ret = False
                fail.update({"error": "key error: %s" % str(e)})
                fail_data.append(fail)
            except Exception as e:
                print '\nerror:'
                print str(e)
                ret = False
                fail.update({"error": str(e)})
                fail_data.append(fail)
 
            # ret = contact_create_or_update([data])

            save_to_redis(parse_record_id, total_count, ret)
            value = cache.get(REDIS_KEY_TEMPLATE.format(parse_record_id))
            record = ParseFileRecord.objects.filter(id=parse_record_id).first()
            total, success, fail = get_value_info(value)
            record.total_count = total
            record.success_count = success
            record.fail_count = fail
            record.status = ParseFileRecord.PARSED_COMPLETE
            record.save()
 
    else:
        for data in sheet_content:
            fail = copy.deepcopy(data)
            print data
            print '\n---\n'
            try:
                data = parse_content(data)    # save single data
                ret = save_content(data, platform, parse_record_id)    # save single data
                if not ret:
                    print("save failed: %s " % data)
                    fail_data.append(fail)
            except Exception as e:
                print '\nerror:'
                print str(e)
                ret = False
                fail.update({"error": str(e)})
                fail_data.append(fail)

            save_to_redis(parse_record_id, total_count, ret)
        else:
            # parse file complete
            # update parse file record
            value = cache.get(REDIS_KEY_TEMPLATE.format(parse_record_id))
            record = ParseFileRecord.objects.filter(id=parse_record_id).first()
            total, success, fail = get_value_info(value)
            record.total_count = total
            record.success_count = success
            record.fail_count = fail
            record.status = ParseFileRecord.PARSED_COMPLETE
            record.save()
    module_records = ParseFileRecord.objects.filter(
        module=record.module,
        status__in=(ParseFileRecord.IN_PARSE_QUEUE, ParseFileRecord.PARSING)
    )
    print "----", module_records
    if len(module_records) == 1:
        print "in module_record", module_records
        module_record = module_records.first()
        # if module_record.id == record.id:
        import_module = ImportModule.objects.filter(id=module_record.module.id).first()
        if import_module:
            import_module.status = 0
            import_module.save()

    if record.module.module_type == ImportModule.REPAIR_MSG:
        record.status = ParseFileRecord.PARSED_COMPLETE
        record.total_count = info_repair.count
        record.success_count = info_repair.success
        record.fail_count = info_repair.fail
        record.save()
    if fail_data:
        if record.module.module_type == ImportModule.REPAIR_MSG:
            fail_file = info_repair.save_fail_data(fail_data)
            record.status = ParseFileRecord.PARSED_FAILED
            record.fail_file = fail_file
            record.save()
        else:
            file_obj, url = save_failed_data(import_file.header, fail_data, import_file, record.id)   # save fail data
            # create upload file obj
            if file_obj:
                fail_file = UploadFile(file_name=file_obj.file_name,
                                       upload_file=file_obj.file_content,
                                       status=UploadFile.FAILED_FILE,
                                       download_url=url)
                fail_file.save()
                record.status = ParseFileRecord.PARSED_FAILED
                record.fail_file = fail_file
                record.save()

    import_module = ImportModule.objects.filter(id=record.module.id).first()
    if import_module:
        import_module.status = 0
        import_module.save()

def delete_redis_key(parse_record_id):
    """
    :param parse_record_id:
    :return:
    """
    key = REDIS_KEY_TEMPLATE.format(parse_record_id)
    cache.delete(key)


def save_to_redis(parse_record_id, total, success=True):
    """
    :param parse_record_id: the ParseFileRecord model id
    :param total: total data count
    :param success: bool, if save success
    :return:
    """
    key = REDIS_KEY_TEMPLATE.format(parse_record_id)
    if cache.get(key):
        # update key
        old_value = cache.get(key)
        print("old_value: %s" % old_value)
        total_count, success_count, fail_count = get_value_info(old_value)
        if success:
            success_count += 1
        else:
            fail_count += 1
    else:
        print("create key %s" % key)
        success_count = 0
        fail_count = 0
    value = VALUE_TEMPLATE.format(total_count=total,
                                  success_count=success_count,
                                  fail_count=fail_count)
    print("set key value %s: %s" % (key, value))
    cache.set(key, value)


def get_value_info(value):
    info = value.split('_')
    total_count = int(info[0][1:])
    success_count = int(info[1][1:])
    fail_count = int(info[2][1:])
    return total_count, success_count, fail_count


def get_parse_progress(parse_record_id):
    key = REDIS_KEY_TEMPLATE.format(parse_record_id)
    print('get key: %s' % key)
    value = cache.get(key)
    print("redis: %s" % value)
    if not value:
        total_count = 0
        success_count = 0
        fail_count = 0
    else:
        total_count, success_count, fail_count = get_value_info(value)
    return {
        "total_count": total_count,
        "success_count": success_count,
        "fail_count": fail_count
    }

def parse_content(content):
    print 'in parse content'
    print content
    # content = {
        # # u'string_bank_name': u'工行',
        # u'string_bank_name': u'中国工商银行',
        # u'int32_real_repay_amount': u'12.34元',
        # u'string_real_repay_time': u'2016年8月9日',
        # # u'string_bank_name': '',
        # # u'string_bank_name': '',
        # u'string_contact_relation2': u'\u5149\u654f\u53ef\u80fd', u'string_contact_relation1': u'fdsa', u'string_name': u'\u9ec4\u677e', u'string_contact_phone1': 12345678901L, u'string_contact_phone2': 22345678901L, u'string_idcard_no': 1.30528198709188e+17, u'string_contact_name1': u'\u975e\u61c2fdsa', u'string_channel': u'adb', u'string_phone': 18761817219L, u'string_contact_name2': u'\u8463\u5144', u'int32_marriaged': u'\u672a\u5a5a'}

    # phone_re_str = r'(1(3[0-9]|4[57]|5[0-35-9]|7[01678]|8[0-9])\d{8}$)'
    phone_re_str = r'(1[34578][0-9]\d{8}$)|(\d{3,4}|\d{3,4}-|\s?\d{7,8})'
    bank_name_re_str = r'(中国工商银行|中国农业银行|中国银行|中国建设银行|交通银行|中信银行|中国光大银行|华夏银行|中国民生银行|广发银行|深圳发展银行|招商银行|兴业银行|上海浦东发展银行|恒丰银行|浙商银行|渤海银行|中国邮政储蓄银行|工商银行|农业银行|建设银行|光大银行|民生银行|邮政储蓄|浦东银行|平安银行|邮政银行|浦东银行|浦发银行)'
    date_re_str = r'(\d{4})[/.\-年]?(\d{1,2})[/.\-月]?(\d{1,2})'
    amount_re_str = r'(\d+\.\d+|\d+)(元)?'
    int_re_str = r'(\d{1,4})'

    date_keys = ['string_should_repay_time', 'string_real_repay_time', 'string_apply_start_time', 'string_apply_end_time', 'string_renew_repay_time', 'string_pay_time']
    re_dic = {
        'string_phone': phone_re_str,
        # 'string_contact_phone1': phone_re_str,
        # 'string_contact_phone2': phone_re_str,
        # 'string_contact_phone3': phone_re_str,
        'string_bank_name': bank_name_re_str,
        'string_bank_card_name': bank_name_re_str,

        'int32_amount': amount_re_str,
        'int32_real_repay_amount': amount_re_str,
        'int32_penalty': amount_re_str,
        'int32_overdue_interest': amount_re_str,
        'int32_should_repay_amount': amount_re_str,
        'int32_real_time_should_repay_amount': amount_re_str,
        'int32_reduction_amount': amount_re_str,

        'int32_installment_count': int_re_str,
        'int32_installment_number': int_re_str,
        'int32_overdue_days': int_re_str,
        'int32_installment_days': int_re_str,

        'string_real_repay_time': date_re_str,
        'string_should_repay_time': date_re_str,
        'string_apply_start_time': date_re_str,
        'string_apply_end_time': date_re_str,
        'string_renew_repay_time': date_re_str,
        'string_pay_time': date_re_str,
    }
    for k,v in content.items():
        # print '--'
        # print k, v
        # print type(v)
        print '09*()' * 10
        print k,v
        if v is None:
            v = ''
        if k not in re_dic or not v:
            continue

        if not isinstance(v, basestring):
            v = str(v).strip()
        else:
            print("----------encode", v)
            print(v)
            v = v.encode('utf8')
        v = v.strip()
        content[k] = v.strip()
        print content[k]
        print type(content[k])

        if k in date_keys:
            print 'in date_keys'
            # 2016-12-20 00:00:00 对应 的 cell 中的数据 42724(天)
            print k, v
            if len(v) < 8:
                v = from_excel(float(v))
                v = str(v)
                print v


        # print type(v)
        # print v
        if 'string_phone' in k:
            print "----string_phone"
            print k, v
            if '.' in v:
                print "float"
                v = int(float(v))
            v = str(v)
            print v
        re_data = re.search(re_dic[k], v)
        if not re_data and v:
            print re_data
            msg =  v + '不可用' 
            msg = v + '  -- 字段 不可用!'
            raise ValueError(msg)

        print re_data.groups()
        content[k] = re_data.groups()[0]
        if k in date_keys:
            year, month, day = [int(d) for d in re_data.groups()]
            try:
                repay_date = datetime(year, month, day)
                content[k] = repay_date.strftime('%Y-%m-%d')
            except Exception as e:
                print e
                raise ValueError("时间格式错误")

    print content
    print 'out parse_content\n'

    return content


def save_content(content, platform, parse_record_id):
    """
    :param content: dict, data
    :return: bool, save success or fail
    """
    # TODO save content
    print 'in save_content'
    user_center_field = ['string_bank_card_id',
                         'string_qq',
                         'string_idcard_front',
                         'string_company_job',
                         'string_bank_card_phone',
                         'string_idcard_reverse',
                         'string_name',
                         'string_idcard_no',
                         'string_family_address',
                         'string_bank_card_name',
                         'string_company_phone',
                         'string_bank_card_username',
                         'string_email',
                         'string_company_address',
                         'string_channel',
                         'string_phone',
                         'int32_is_student',
                         'string_company',
                         'int32_marriaged',
                         'string_idcard_hand']

    repayment_field = ['int32_penalty', 'int32_should_repay_amount', 'int32_overdue_interest', 'int32_amount', 'int32_real_repay_amount', 'int32_real_time_should_repay_amount', 'int32_reduction_amount']
    exclude_field = ["int32_installment_count", "int32_installment_number", "string_should_repay_time", "string_real_repay_time", "int32_overdue_days", "int32_penalty", "int32_should_repay_amount", "int32_overdue_interest", "string_order_number", "int32_real_repay_amount", "string_repay_status", 'int32_real_time_should_repay_amount','string_apply_start_time', 'string_apply_end_time']

    print("save content: %s" % content)
    contact_info = {"contact_list": []}
    contact_list = []
    for k, v in content.items():
        if isinstance(v, str):
            v = v.strip()
        if v is None:
            v = ''
        if k in user_center_field:
            if isinstance(v, (float, int, long)):
                v = str(int(v)).strip()
            if v is None:
                v = ''
            if isinstance(v, unicode):
                print("unicode: %s", v)
                v = v.encode("utf-8").strip()
                print("unicode encode: %s", v)
        if isinstance(v, (datetime, date)):
            v = v.strftime("%Y-%m-%d")
        if "marriaged" in k:
            if '已' in v:
                v = 2
            elif '未' in v:
                v = 1
            else:
                v = 0
        contact_info[k] = v
        # 联系人信息独立处理
        if "string_contact" in k:
            contact_list.append((k, v))
            contact_info.pop(k, None)

    print("contact_list: %s" % contact_list)
    print content
    contact_list.sort(key=lambda item: int(item[0][-1]))
    # print contact_list
    contact_step = 3
    if content.get('string_channel') in [u'蓝领贷']:
        contact_step = 1

    for info in range(0, len(contact_list), contact_step):
        ret = [''] * 4
        # print info
        for i in range(info, info+contact_step):
            try:
                contact_list[i]
            # except:
                # break
                print("contact list: %s" % contact_list[i][0])
                value = contact_list[i][1]
                print("contact value: %s, type: %s" % (value, type(value)))
                if isinstance(value, unicode):
                    value = value.encode("utf-8")
                if "relation" in contact_list[i][0]:
                    if not isinstance(value, str):
                        ret[0] = str(value)
                    else:
                        ret[0] = value
                elif "phone" in contact_list[i][0]:
                    if isinstance(value, str) and '.' in value:
                        ret[1] = str(int(float(value)))
                    ret[1] = str(value)
                elif "name" in contact_list[i][0]:
                    if not isinstance(value, str):
                        ret[2] = str(value)
                    else:
                        ret[2] = value
                elif "add" in contact_list[i][0]:
                    ret[3] = value
            except Exception as e:
                print e

        if ret[1]:
            contact_info['contact_list'].append(ret)
    print("contact_info: %s" % contact_info)
    # 贷款数据不写入, 进件系统
    user_data = copy.deepcopy(contact_info)
    for k in exclude_field:
        user_data.pop(k, None)
    # repayment_info = {k: int(float(contact_info.pop(k)) * 100)  for k in repayment_field if contact_info.get(k)}
    if user_data.get('int32_amount'):
        user_data['int32_amount'] = int(float(user_data['int32_amount']) * 100)

    user_data['string_platform'] = str(platform)

    # 回款时, 只需要少量的字段, 其他的字段从 db 中直接取
    print '---------\n\n'
    print user_data
    print content
    if content.get('string_order_number'):
        q = dict(
            order_number=content.get('string_order_number'),
            user__channel=content.get('string_channel'),
            # capital_channel_id=repayment_data['capital_channel_id'],
        )
        repayment = RepaymentInfo.objects.filter(**q).first()
        print '*' * 100
        print repayment
        if repayment:
            user_data['string_idcard_no'] = user_data.get('string_idcard_no') or repayment.user.id_no
            user_data['string_phone'] = user_data.get('string_phone') or repayment.user.phone_no
    elif content.get('string_idcard_no'):
        id_no = content.get('string_idcard_no')
        channel = content.get('string_channel')
        user = User.objects.filter(id_no=id_no, channel=channel).first()
        if user:
            user_data['string_phone'] = user.phone_no


    user_ret = client.import_user_data(**user_data)
    # user_ret = None
    print("save user_ret: %s" % user_ret)
    repayment_info = {}
    for k, v in contact_info.items():
        if k in repayment_field and v:
            v = int(float(v) * 100)
            # if isinstance(v, (float, int, long)):
            # elif isinstance(v, basestring):
                # v = int(int(v * 100)

        if v is None:
            v = ''
        if isinstance(v, (datetime, date)):
            print("-----------encode: ", v)
            v = v.strftime("%Y-%m-%d")
        repayment_info[k] = v
    if not user_ret:
        raise ValueError("存储用户错误")
    if user_ret.retcode == 0 and not repayment_info.get('string_order_number'):
        repayment_info['string_order_number'] = user_ret.user_id
    print('repayment_info: %s' % repayment_info)
    other_ret = repayment_create_or_update(repayment_info, platform, parse_record_id)
    # other_ret = dict(code=0)
    print("save repayment_ret: %s" % other_ret)
    if not user_ret or not other_ret:
        raise ValueError("存储错误: " + str(user_ret.errmsg) + str(other_ret['msg']))
        return False
    if user_ret.retcode == 0 and other_ret['code'] == 0:
        return True
    else:
        raise ValueError("存储错误: " + str(user_ret.errmsg) + str(other_ret['msg']))
        print("save error: %s" % user_ret.errmsg)
        return False


def save_failed_data(header, content, import_file, record_id):
    # save fail data
    # print("save failed data header: %s context: %s" % (header, content))
    if content:
        file_path = import_file.virtual_save(content, record_id)
        res = requests.post('%sfile' % settings.IMAGE_SERVER_URL, files = {'file': file_path.file_content}, data = {'type': 'xlsx'})
        result = res.json()
        print("----", result)
        #response = JsonResponse({'code': 0, 'url': result['url']})
        return file_path, result['url']


class InfoRepairImport(object):

    idcard_sys = 'string_xinxiu_our_idno'
    channel_sys = 'string_xinxiu_channel'
    our_phone = 'string_xinxiu_ourphone'

    def __init__(self, record_id, user):
        self.record_id = record_id
        self.user = user
        self.en_cn_map = None
        self.count = 0
        self.success = 0
        self.fail = 0
        self.separator = ','

    def save_repair_msg(self, data, platform, module_id):
        self.en_cn_map, separator = get_header(module_id)
        self.separator = separator
        # import ipdb; ipdb.set_trace()
        data = self.merge_data(data, separator)
        self.count = len(data)
        fail_data = []
        for line in data:
            id_no = line[self.idcard_sys]
            channel = line[self.channel_sys]
            app = Apply.objects.filter(
                create_by__id_no=str(id_no[0]).strip(), create_by__channel=channel[0].strip(),
                platform=platform, status=Apply.LOST_CONTACT
            ).first()
            if not app:
                print("----- can't find apply ------")
                print(id_no, channel)
                line['error'] = u"没有对应订单"
                fail_data.append(line)
                self.fail += 1
                continue
            try:
                self.processing_repair_msg(app, line)
            except Exception as e:
                line['error'] = u"修复信息错误: %s" % e
                fail_data.append(line)
                continue
        return fail_data
        # self.save_fail_data(fail_data)

    def processing_repair_msg(self, app, line):
        line_info = copy.deepcopy(line)
        line_info.pop(self.idcard_sys)
        line_info.pop(self.channel_sys)
        line_info.pop(self.our_phone)
        if not any(line_info):
            # 召回失败
            app.status = Apply.RECALL_FAIL
            app.save()
            self.success += 1
            # 上报 催记
            note = app.get_status_display()
            collection_record = dict(
                record_type=CollectionRecord.LOST_CONTACT,
                collection_note=note,
                create_by=self.user,
                apply=app
            )
            CollectionRecord.objects.create(**collection_record)
            report_collection(app, note)
            return
        for key, value in line.items():
            print "---", key, value
            if key in (self.idcard_sys, self.channel_sys, self.our_phone):
                continue
            is_must = False
            if 'phone' in key:
                is_must = True
            for item in value:
                if isinstance(item, (unicode, str)):
                    item = item.strip()
                if not item:
                    print item
                    continue
                data = {"is_must": is_must, "cn_name": self.en_cn_map.get(key), "content": item}
                save_or_update_field(app, data)
        else:
            app.status = Apply.RECALL_SUCCESS
            app.save()
            # 上报 催记
            note = app.get_status_display()
            collection_record = dict(
                record_type=CollectionRecord.LOST_CONTACT,
                collection_note=note,
                create_by=self.user,
                apply=app
            )
            CollectionRecord.objects.create(**collection_record)
            report_collection(app, note)
        self.success += 1

    @classmethod
    def merge_data(cls, data, separator):
        """
        合并重复信息，将多条信息合并到一条
        以身份证为唯一标示合并
        """
        print data
        ret = {}
        for item in data:
            id_no = item[cls.idcard_sys]
            if ret.get(id_no):
                for k, v in item.iteritems():
                    if not isinstance(v, (str, unicode)):
                        if not v:
                            continue
                        v = str(v)
                    v = cls.process_special_key(k, v)
                    if ret[id_no].get(k):
                        ret[id_no][k] = list(set(v.split(separator)) | set(ret[id_no][k]))
                    else:
                        ret[id_no][k] = v.split(separator)
            else:
                new_item = {}
                for k, v in item.iteritems():
                    if not isinstance(v, (str, unicode)):
                        if not v:
                            continue
                        v = str(v)
                    v = cls.process_special_key(k, v)
                    new_item[k] = v.split(separator)
                ret[id_no] = new_item
        print ret
        return ret.values()

    @classmethod
    def process_special_key(cls, k, v):
        """
        特殊字段特殊处理
        ABCDEFGHIJ对应1234567890
        """
        special_key = (
            "string_xinxiu_social_phone",
            "string_xinxiu_bairong_phone",
            "string_xinxiu_bairong_telephone"
        )

        def process_special_phone(v):
            ret = []
            for item in v:
                if ord('A') <= ord(item) < ord('J'):
                    ret.append(str(ord(item) - ord('A') + 1))
                elif item == 'J':
                    ret.append('0')
                else:
                    ret.append(item)
            return ''.join(ret)
        if k in special_key:
            return process_special_phone(v)
        return v

    def save_fail_data(self, fail_data):
        content = [{k: self.separator.join(v) for k, v in item.iteritems()} for item in fail_data]
        name, fail_file = ImportFile.save_fail_file(content, self.record_id, self.en_cn_map)
        res = requests.post(
            '%sfile' % settings.IMAGE_SERVER_URL,
            files={'file': fail_file}, data={'type': 'xlsx'})
        result = res.json()
        file_ = UploadFile.objects.create(file_name=name,
                                          upload_file=fail_file,
                                          status=UploadFile.FAILED_FILE,
                                          download_url=result['url'])
        return file_


def get_header(module_id):
    fileds = ImportField.objects.filter(module_id=module_id)
    separator = ','
    if fileds:
        module = fileds.first().module
        # TODO hard code 每个分隔符都不一样
        if u"同盾" in module.name:
            separator = ','
        elif u"百融" in module.name:
            separator = u"、"
    ret = {item.sys_field_id.name: item.user_field_name for item in fileds}
    ret['error'] = 'error'
    return ret, separator


def save_or_update_field(app, data):
    exsit_field = InfoField.objects.filter(cn_name=data['cn_name'], content=data['content'], user=app.create_by)
    if not exsit_field:
        module = InfoModule.objects.filter(field_name=data['cn_name']).first()
        module_name = module.cn_name if module else u"默认"
        InfoField.objects.create(
            cn_name=data['cn_name'], content=data['content'],
            user=app.create_by, info_module=module_name, is_must=data['is_must']
        )
