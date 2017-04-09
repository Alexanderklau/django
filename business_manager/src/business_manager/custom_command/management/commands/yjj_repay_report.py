# -*- coding: utf-8 -*-
"""
数据导入模板:
    创建 profile field, profile module
"""


from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q

import os, traceback, random
from datetime import datetime
import time
import json
import re

from business_manager.review import message_client, risk_client, redis_client
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord
from business_manager.collection.models import *

from business_manager.config_center.models import *

from business_manager.strategy.models import Strategy2
from business_manager.import_data.services import report_data_collection_money
import copy

yjj_str = u"""张玉琴,LN2017011919010248,易借金,2017年2月14日,1320.00;陈壮,LN2017011910153019,易借金,2017年2月14日,1300.00;邓良海,LN2016081812183745,易借金,2017年2月13日,1300.00;张福日,LN2016112310064059,易借金,2017年2月13日,1280.00;袁飞,LN2017011810064492,易借金,2017年2月13日,1300.00;李钰,LN2017011110170940,易借金,2017年2月13日,200.00;文亮亮,LN2017011210105378,易借金,2017年2月4日,1260;王黎兵,LN2017011921242186,易借金,2017年2月4日,1120;郭毅滨,LN2016121510195466,易借金,2017年2月4日,1260;侯春虎,LN2016112210140078,易借金,2017年2月9日,220;谢鑫,LN2017011110471617,易借金,2017年2月8日,380;梁宵,LN2017012010021668,易借金,2017年2月8日,1160;冯明峰,LN2016092110004727,易借金,2017年2月8日,1220;张云,LN2017011610033138,易借金,2017年2月11日,1320;陈效松,LN2017010510125790,易借金,2017年2月11日,260"""
lld_str = u"""张峥,421081199601032277,蓝领贷,2017年2月6日,2680;何云,650204198508200024,蓝领贷,2017年2月7日,1880;姜鸽,650105198901090010,蓝领贷,2017年2月6日,960;张玉良,330483199403052316,蓝领贷,2017年2月7日,1840;曲一航,230126199408291618,蓝领贷,2017年2月7日,1880;蒋陶,510132199002222916,蓝领贷,2017年2月7日,1880;程伟泽,350521199410216059,蓝领贷,2017年2月7日,1880;李琛,120221199410220315,蓝领贷,2017年2月7日,1880;顾晨波,330424199706262011,蓝领贷,2017年2月7日,1900;翟振然,410182199501174111,蓝领贷,2017年2月7日,1840;陈哲,410702199109260016,蓝领贷,2017年2月7日,1920;翁杨南,321324199408154016,蓝领贷,2017年2月8日,1500;王小龙,340123198309107776,蓝领贷,2017年2月6日,1960;胡李杰,330324199009085050,蓝领贷,2017年2月8日,1680;黄种地,350583199311295512,蓝领贷,2017年2月8日,1920;肖子俊,440184199004021817,蓝领贷,2017年2月9日,1560;李敏儿 ,441900199105223829,蓝领贷,2017年2月9日,1750;林巧珍,445281199012045828,蓝领贷,2017年2月9日,1660;张茂伟,340322198804131612,蓝领贷,2017年2月9日,1600;郝鹏程,210221199801136016,蓝领贷,2017年2月9日,1960;刘斌 ,430405199004075013,蓝领贷,2017年2月10日,1800;谢建辉,441283198802140015,蓝领贷,2017年2月9日,1940;梁锦龙,440803198912161116,蓝领贷,2017年2月9日,1860;史晓文,632124199305011218,蓝领贷,2017年2月10日,1740;陈松,51303019930315021X,蓝领贷,2017年2月10日,1980;曾莉,360729199106040021,蓝领贷,2017年2月10日,1920;张真杰,331022199505042414,蓝领贷,2017年2月9日,1880;朱华强 ,371524199605154939,蓝领贷,2017年2月10日,1780;黄泳麟,44018119940310061X,蓝领贷,2017年2月10日,1880;焦文哲,130127199208200075,蓝领贷,2017年2月9日,1580;吴京洲,441422198706240014,蓝领贷,2017年2月10日,1880;王珏,341126199604147011,蓝领贷,2017年2月9日,1840;谢乃体,450121199110034538,蓝领贷,2017年2月9日,1960;杨竞贻,430726199311121030,蓝领贷,2017年2月10日,1550;樊益波,321283198501069211,蓝领贷,2017年2月10日,1920;林毅,332522199005202977,蓝领贷,2017年2月13日,1620;陈灿,500222199105108623,蓝领贷,2017年2月11日,1700;杨刚,370284198608310030,蓝领贷,2017年2月11日,1960;林玉蝶,460005199708253264,蓝领贷,2017年2月10日,2060;刘小梅,430781197311046224,蓝领贷,2017年2月13日,2000;其根,152530199003043227,蓝领贷,2017年2月13日,1920;李志龙,350500199307225035,蓝领贷,2017年2月12日,1960;黄勇,510181198201081311,蓝领贷,2017年2月11日,2140;杨晶,320981199301174729,蓝领贷,2017年2月13日,2000;刘华顺,210881199104185858,蓝领贷,2017年2月6日,1060;徐名杜,430726199611080015,蓝领贷,2017年2月14日,2060;赵丹丹,410881199107110760,蓝领贷,2017年2月13日,1900;姚少武,440582199105121592,蓝领贷,2017年2月14日,2060;崔宇,412728198510200010,蓝领贷,2017年2月14日,2060;鄢秀斌,362301198606224037,蓝领贷,2017年2月10日,2020;杨华军,51090219870923185X,蓝领贷,2017年2月14日,2040;王亚军 ,410481198904122039,蓝领贷,2017年2月14日,1750;陈金洲,320882198707303259,蓝领贷,2017年2月7日,2080;熊苏丹,341125198411171452,蓝领贷,2017年2月15日,2060;赵袁欢,320322198902063410,蓝领贷,2017年2月12日,1980;黄鑫,500234199306082736,蓝领贷,2017年2月15日,1560;田盛翼,430802199802284410,蓝领贷,2017年2月15日,1800"""

def parse_text(text):
    date_re_str = ur'(\d{4})[/.\-年]?(\d{1,2})[/.\-月]?(\d{1,2})[日]?'

    lines = text.split(';')
    datas = [_l.split(',') for _l in lines]
    for data in datas:
        pass
        re_data = re.search(date_re_str, data[3])
        year, month, day = [int(d) for d in re_data.groups()]
        try:
            real_repay_time = datetime(year, month, day)
            data[3] = real_repay_time
        except Exception as e:
            print e
            raise ValueError("时间格式错误")

    print datas
    return datas


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            # datas = parse_text(yjj_str)
            datas = parse_text(lld_str)
            for data in datas:
                print data
                # 蓝领贷, order_number 是身份证号
                name, order_number, channel, real_repay_time, amount = data
                amount = int(float(amount) * 100)
                print name, order_number, channel, real_repay_time, amount
                q = {
                    # 'order_number': order_number,
                    'user__id_no': order_number,
                    'user__name': name,
                    'user__channel': channel,
                }
                repayment = RepaymentInfo.objects.filter(**q).first()
                collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(type__in=["a", "b", "c", "d", "e", 'g', 'h'])).order_by('-id')
                print repayment
                print collection_apply
                report_data_collection_money(collection_apply.first(), rest_repay_money=amount, recover_date=real_repay_time)
                # return
            # [u'\u674e\u56fd\u7115', u'LN2016102610370012', u'\u6613\u501f\u91d1', datetime.datetime(2016, 12, 24, 0, 0), u'160.00']

        except Exception, e:
            print e

