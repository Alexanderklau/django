# -*- coding:utf-8 -*-
import datetime
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

from django.core.management.base import BaseCommand

from business_manager.order.apply_models import Apply
from business_manager.review.models import CollectionRecord
from business_manager.collection.models import InstallmentDetailInfo
from pyExcelerator import *


class Command(BaseCommand):
    def handle(self, *args, **options):
        try:
            start_date = datetime.datetime.strptime(args[0], '%Y-%m-%d')
            end_date = datetime.datetime.strptime(args[1], '%Y-%m-%d')
        except Exception as e:
            print('wrong args: %s' % e)
            return
        text = self.export(start_date, end_date)
        self.export_to_file(text)

    def export_data(self, start_date):
        ret = []
        m1_data = Apply.objects.filter(create_at__gte=start_date,
                                       status__in=(Apply.COLLECTION_SUCCESS, Apply.REPAY_SUCCESS))
        for data in m1_data:
            col = CollectionRecord.objects.filter(apply=data,
                                                  record_type=CollectionRecord.DISPATCH).order_by("-id").first()
            if col:
                employee = str(col.create_by)
            else:
                employee = ''
            ret.append({'create_at': data.create_at.strftime('%Y-%m-%d'), 'update_at': data.update_at.strftime('%Y-%m-%d'),
                        'money': data.money, 'order_number': data.repayment.order_number,
                        'employee': employee, 'status': 'm1'})
        return ret

    def export(self, start_date, end_date):
        ret = []
        query_ret = InstallmentDetailInfo.objects.filter(real_repay_time__gte=start_date,
                                                         real_repay_time__lt=end_date,
                                                         repay_status__in=(3, 8, 9))
        for info in query_ret:
            app = Apply.objects.filter(repayment=info.repayment, real_repay_time=info.real_repay_time).first()
            apply_type = 'm1'
            if app:
                col = CollectionRecord.objects.filter(apply=app,
                                                      record_type=CollectionRecord.DISPATCH).order_by("-id").first()
                employee = col.create_by.username if col else 'no collector'
                username = app.create_by.name

                if app.type == 'b':
                    apply_type = 'm1'
                elif app.type == 'c':
                    apply_type = 'm2'
                elif app.type == 'd':
                    apply_type = 'm3'
            else:
                employee = 'no collector'
                username = 'no username'
            if info.create_at:
                create_at = info.create_at.strftime('%Y-%m-%d')
            elif app:
                create_at = app.create_at.strftime('%Y-%m-%d')
            else:
                create_at = 'no record'

            ret.append({"create_at": create_at, 'update_at': info.real_repay_time.strftime('%Y-%m-%d'),
                        "money": round(info.real_repay_amount/100.0, 2), 'order_number': info.repayment.order_number,
                        "username": username, "employee": employee, 'overdue_days': str(info.overdue_days),
                        "type": apply_type})
        return ret

    def export_to_file(self, data):
        w = Workbook()
        ws = w.add_sheet('sheet1')
        ws.write(0, 0, u'进件日期')
        ws.write(0, 1, u'回款日期')
        ws.write(0, 2, u'回款金额')
        ws.write(0, 3, u'工单号')
        ws.write(0, 4, u'姓名')
        ws.write(0, 5, u'催收员')
        ws.write(0, 6, u'逾期天数')
        ws.write(0, 7, u'类型')

        for i, item in enumerate(data):
            ws.write(i + 1, 0, item['create_at'])
            ws.write(i + 1, 1, item['update_at'])
            ws.write(i + 1, 2, item['money'])
            ws.write(i + 1, 3, item['order_number'])
            ws.write(i + 1, 4, item['username'])
            ws.write(i + 1, 5, item['employee'])
            ws.write(i + 1, 6, item['overdue_days'])
            ws.write(i + 1, 7, item['type'])

        w.save('/home/admin/rst/export_data/hk.xls')

