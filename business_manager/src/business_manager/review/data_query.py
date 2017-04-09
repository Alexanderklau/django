# -*- coding: utf-8 -*-
################################################################################
#
# Copyright (c) 2015 hualahuala.com, All Rights Reserved
#
################################################################################

import json
import traceback
import urllib, urllib2
from django.conf import settings
from business_manager.python_common.log_client import CommonLog as Log
from copy import deepcopy
from business_manager.order.models import AddressBook
#from business_manager.common.dict import dict_addcount, dict_addmap

def dict_addmap(my_dict, key):
    if not key in my_dict:
        my_dict[key] = {}

def get_dataserver_result(data, env="online", timeout=2):
    param = json.dumps(data)
    if env == "pre":
        #url = "http://121.43.146.31:8888/query"
        #url = "https://data.hualahuala.com/query"
        # url = "http://121.40.167.184:8888/query"
        url = "http://120.27.194.169:8888/query"
    else:
        url = settings.DATA_SERVER["URL"] + 'query'
    headers = {'Content-Type': 'application/json'}
    try:
        req = urllib2.Request(url = url, headers = headers)
        rsp = urllib2.urlopen(req, data=param, timeout=timeout).read()
    except Exception, e:
        Log().error("get dataserver error %s" % e)
        return None

    if rsp:
        return json.loads(rsp)
    else:
        print "response is None"
        return None

def _get_featrue(data, featrue_name):
    for featrue in data:
        if featrue["name"] == featrue_name:
            return featrue
    return None

def get_phonecall_rawdata(data):
    '''
        return:
    '''
    try:
        result = get_dataserver_result(data=data, timeout=20)
        if result["success"]:
            feature = _get_featrue(result["feature_list"], "phone_call_record")
            if feature["is_ok"]:
                #print feature["description"], ":", feature["value"]
                #print len(feature["value"])
                return feature["value"]
            else:
                #print feature["name"], feature["status"]
                return feature["status"]
        else:
            print "get result failed", result["err_code"],  result["err_message"]
            return {"is_ok":False, "status":"采集失败"}
    except Exception, e:
        return {"is_ok":False, "status":"采集失败"}

def get_phone_location_data(data):
    try:
        result = get_dataserver_result(data=data, timeout=20)
        if not result:
            return {"is_ok":False, "status":"采集失败"}
        if result["success"]:
            feature = _get_featrue(result["feature_list"], "location_info")
            return feature
        else:
            print "get result failed", result["err_code"],  result["err_message"]
            return {"is_ok":False, "status":"采集失败"}
    except Exception, e:
        print "get location failed", e
        return {"is_ok":False, "status":"采集失败"}


def get_phonebasic_data(data):
    '''
        return: [{"is_ok":True, "status":"采集完成", "name":"f1", "value":"v1", "description":"desc"}, {...}]
    '''
    try:
        result = get_dataserver_result(data)
        if not result:
            return None
        if result["success"]:
            return result["feature_list"]
        else:
            print "get result failed", result["err_code"],  result["err_message"]
            return result["feature_list"]
    except Exception, e:
        return {"is_ok":False, "status":"采集失败"}

def _time_trans(time):
    if not time:
        return ""
    hour = time / 3600
    minute = time % 3600 / 60
    second = time % 60
    return "%s:%s:%s" % (hour, minute, second)

def get_corp_phonecall_data(data):
    '''
        return:
    '''
    try:
        result = get_dataserver_result(data)

        phone_calls = {}
        phone_types = [u"电话", u"公司"]
        data_size = len(data["feature_list"])  # feature中去掉 corp_contact 加上 公司
        offset = 1

        if not result:
            return None, None
        if result["success"]:
            feature = _get_featrue(result["feature_list"], "corp_contact")
            if not feature:
                print "corp not found: "
                return None
            for corp in feature["value"]:
                if not corp["contact_tel"] in phone_calls:
                    phone_calls[corp["contact_tel"]] = [" "] * (data_size)
                phone_calls[corp["contact_tel"]][0] = corp["corp_name"]

            # 干掉 "corp_contact":

            feature_data = deepcopy(data["feature_list"])
            feature_data.pop(0)
            for index, feature_name in enumerate(feature_data):
                feature = _get_featrue(result["feature_list"], feature_name)
                if feature["is_ok"]:
                    phone_types.append(feature["description"])
                    for phone in feature["value"]:
                        if not phone["contact_tel"] in phone_calls:
                            continue
                        if feature_name == "call_time" or feature_name == "call_passive_time":
                            phone_calls[phone["contact_tel"]][index + offset] = _time_trans(phone["value"])
                        else:
                            phone_calls[phone["contact_tel"]][index + offset] = phone["value"]
                else:
                    phone_types.append(feature["description"])
                    # print feature["name"], feature["status"]
                    pass
            return (phone_calls, phone_types)
        else:
            Log().error("get_corp_phonecall_data get result failed %s %s" % (result["err_code"],  result["err_message"],))
            print "get result failed", result["err_code"],  result["err_message"]
            return (None, None)
    except Exception, e:
        print str(e)
        return (None, None)

def _relationship_trans(relation):
    if relation == -1:
        return u""
    elif relation == 1:
        return u"父亲"
    elif relation == 2:
        return u"母亲"
    elif relation == 3:
        return u"配偶"
    elif relation == 4:
        return u"亲戚"
    elif relation == 5:
        return u"朋友"
    elif relation == 6:
        return u"同事"
    elif relation == 7:
        return u"同学"
    elif relation == 8:
        return u"其他"
    else:
        return u"未知"

def get_phonecall_data(data):
    '''
        return:
    '''
    try:
        result = get_dataserver_result(data)
        phone_calls = {}
        phone_types = [u"序号", u"电话",  u"关系", u"通讯录中的姓名"]
        data_size = (len(data["feature_list"]) + 3)                   # feature中去掉 intimate_contact 加上 姓名和关系

        offset = 4
        if not result:
            return None, None
        if result["success"]:
            #print result
            feature = _get_featrue(result["feature_list"], "intimate_contact")
            print 'intimate_contact',feature
            if not feature:
                return None, None

            user_data = {}
            for meta in data['contact']:
                user_data[meta['contact_tel']] = meta['contact_type']

            index = 0
            for contact in feature["value"]:
                index += 1
                name_inaddressbook = AddressBook.objects.filter(owner__id=data["user_id"],
                                                                phone_number=contact["contact_tel"])

                addressbook_name = name_inaddressbook[0].name if name_inaddressbook else ' '
                if contact["contact_tel"] not in phone_calls:
                    phone_calls[contact["contact_tel"]] = [" "] * (data_size)
                    phone_calls[contact["contact_tel"]][0] = index
                    phone_calls[contact["contact_tel"]][1] = contact["contact_tel"]

                    phone_calls[contact["contact_tel"]][2] = _relationship_trans(user_data[contact["contact_tel"]]) if user_data.has_key(contact["contact_tel"]) else  ' '
                    phone_calls[contact["contact_tel"]][3] = addressbook_name
                else:
                    phone_calls[contact["contact_tel"]][1] = contact["contact_tel"]
                    phone_calls[contact["contact_tel"]][2] = _relationship_trans(user_data[contact["contact_tel"]]) if user_data.has_key(contact["contact_tel"]) else  ' '
                    phone_calls[contact["contact_tel"]][3] = addressbook_name

            # 干掉 "intimate_contact":
            feature_data = deepcopy(data["feature_list"])
            feature_data.pop(0)
            for index, feature_name in enumerate(feature_data):
                feature = _get_featrue(result["feature_list"], feature_name)
                if feature["is_ok"]:
                    phone_types.append(feature["description"])
                    for phone in feature["value"]:
                        if not phone["contact_tel"] in phone_calls:
                            continue
                        if feature_name == "call_time" or feature_name == "call_passive_time":
                            phone_calls[phone["contact_tel"]][index + offset] = _time_trans(phone["value"])
                        else:
                            phone_calls[phone["contact_tel"]][index + offset] = phone["value"]
                else:
                    phone_types.append(feature["description"])
                    pass
            return sorted(phone_calls.items(), key = lambda a:a[1][0]), phone_types
        else:
            Log().error("get_phonecall_data get result failed %s %s" % (result["err_code"],  result["err_message"]))
            print "get result failed", result["err_code"],  result["err_message"]
            return None, None
    except Exception, e:
        Log().error(traceback.format_exc())
        traceback.print_exc()
        return (None, None)

def get_deliver_data(data):
    '''
        return:
        [{"predict_addr_type":"xxx", "begin_date":"2015", "end_date":"2015", "total_amount":1, "total_count":1, "address":"xyz",
          "receiver_list":[{"name":"xxx", "phone_num":313123}]},
         {...}]
    '''
    try:
        result = get_dataserver_result(data)
        #print "deliver", result
        if not result:
            return {"is_ok":False, "status":"采集失败"}
        if result["success"]:
            # deliver
            e_deliver = _get_featrue(result["feature_list"], "deliver_address")
            return e_deliver
            #print e_deliver["description"], ":"
            #for address in e_deliver["value"]:
            #    print "\t", address["predict_addr_type"], address["begin_date"], address["end_date"], address["total_amount"], address["total_count"], address["address"]
            #    for receiver in address["receiver_list"]:
            #        print "\t\t", receiver["name"], receiver["phone_num"]
            #return e_deliver["value"]
        else:
            print "get result failed", result["err_code"],  result["err_message"]
            return {"is_ok":False, "status":"采集失败"}
    except Exception, e:
        print e
        return {"is_ok":False, "status":"采集失败"}

def get_ebusiness_data(data):
    '''
        return: [{"is_ok":True, "status":"采集完成", "website":, "real_name":, "is_validate_real_name":, "register_date"}, {...}]
    '''
    try:
        result = get_dataserver_result(data)
        if not result:
            return {"is_ok":False, "status":"采集超时"}

        if result["success"]:
            #basic
            e_basic = _get_featrue(result["feature_list"], "ebusiness_basic")
            return e_basic
        else:
            print "get result failed", result["err_code"],  result["err_message"]
            return "failed"
    except Exception, e:
        print e
        return {"is_ok":False, "status":"采集超时"}


#查询请求
basic_data = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    "feature_list":[ "mobile_name", "is_real_name", "mobile_reg_time", "moblie_unused_time"],
}

phone_data = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    # intimate_contact 必须第一个其他的随意
    "feature_list":["intimate_contact", "call_count", "call_passive_count", "call_time", "call_passive_time", "call_first_date", "call_last_date", "call_day_count"],
}

ebusiness_data = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    "feature_list":["ebusiness_basic"],
}

deliver_data = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    "feature_list":["deliver_address"],
}

corp_data = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    "feature_list":["corp_contact", "call_count", "call_passive_count", "call_time", "call_passive_time", "call_first_date", "call_last_date", "call_day_count"],
}

phone_location_data = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    "feature_list":["location_info"],
}

phonecall_rawdata = {
    "org_account": settings.DATA_SERVER["ORG_NAME"],
    "feature_list":["phone_call_record"],
}

#测试数据查询请求
test_data = {
    "org_account": "hualahuala",
    "user_id": "3342",
    "feature_list":[ "mobile_name", "is_real_name", "mobile_reg_time", "moblie_unused_time"],
}

test_data2 = {
    "org_account": "hualahuala",
    "user_id": "3342",
    # intimate_contact 必须第一个其他的随意
    "feature_list":["intimate_contact", "call_count", "call_passive_count", "call_time", "call_passive_time", "call_first_date", "call_last_date", "call_period", "call_day_count"],
    "contact":[
        {
            "contact_name":"fuck",
            "contact_tel":"1313131313131",
            "contact_type":1
        },
        {
            "contact_name":"bbb",
            "contact_tel":"2121212121212",
            "contact_type":2
        },
        {
            "contact_name":"ccc",
            "contact_tel":"23232323232323",
            "contact_type":3
        }
    ]
}

test_data3 = {
    "org_account": "hualahuala",
    "user_id": "14172",
    "feature_list":["ebusiness_basic"],
}

test_data4 = {
    "org_account": "hualahuala",
    "user_id": "14172",
    "feature_list":["deliver_address"],
}

test_data5 = {
    "org_account": "hualahuala",
    "user_id": "14172",
    "feature_list":["corp_contact", "call_count", "call_passive_count", "call_time", "call_passive_time", "call_first_date", "call_last_date", "call_period", "call_day_count"],
}

test_data6 = {
    "org_account": "hualahuala_yufa",
    "user_id": "26121",
    "feature_list":["location_info"],
}

test_data7 = {
    "org_account": "hualahuala",
    "user_id": "14172",
    "feature_list":["phone_call_record"],
}

if __name__ == '__main__':
    #settings.configure()
    #print get_phonebasic_data(test_data)
    #print get_phonecall_data(test_data2)
    #print get_ebusiness_data(test_data3)
    #print get_deliver_data(test_data4)
    #print get_corp_phonecall_data(test_data5)
    #get_phonecall_rawdata(test_data7)
    print get_phone_location_data(test_data6)

