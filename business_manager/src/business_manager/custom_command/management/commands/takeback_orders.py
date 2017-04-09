# -*- coding:utf-8 -*-
import datetime
from django.core.management import BaseCommand

from business_manager.order.apply_models import Apply
from business_manager.employee.models import Employee

class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        args[0] the date of recyclable orders
        args[0] date format like "2016-10-8"
        """
        self.takeback_employee_orders()
       #if len(args) < 2:
       #    print('no input')
       #    return
       #recycle_date = datetime.datetime.strptime(args[0], "%Y-%m-%d")
       #end_date = datetime.datetime.strptime(args[1], "%Y-%m-%d")
       #self.takeback_orders(recycle_date, end_date)

    def takeback_orders(self, recycle_date, end_date):
        apps = Apply.objects.filter(create_at__gte=recycle_date, create_at__lte=end_date, overdue_days=1)
        apps = Apply.objects.filter(create_at__gte=recycle_date, create_at__lte=end_date, status=Apply.PROCESSING, overdue_days=1)
        import pdb; pdb.set_trace()
        for app in apps:
            app.status = Apply.WAIT
            app.employee = None
            app.save()
        print('done')

    def update_apply(self, start_date, end_date):
        apps = Apply.objects.filter(create_at__gte=start_date, create_at__lte=end_date, overdue_days=1)
        import pdb; pdb.set_trace()
        count = 1
        for app in apps:
            if app.repayment.repay_status == 8:
                count += 1
                print("app: %s" % app.id)
                app.status = 9
                app.save()
        print("done %s" % count)

    def takeback_employee_orders(self):
        employee = Employee.objects.filter(id=3).first()
        apps = Apply.objects.filter(employee=employee, status=Apply.PROCESSING)
        import pdb; pdb.set_trace()
        for app in apps:
            app.status = Apply.WAIT
            app.employee = None
            app.save()
        print('done')

