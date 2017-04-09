# coding=utf-8
import requests
import json
import urllib
import urllib2
# import tablib
# import round
import datetime
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import ExtraApply, Apply
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo
from business_manager.audit.data_views import ReceivablesProvider, ReceivedProvider



def show_financial_report(request):
    if request.method =="GET":
        request_type = request.GET.get('request_type')
        if request_type == 'receivables':
            provider = ReceivablesProvider()
            q_set = provider.object_filter(request)
            print 'aaaaaaaa'
            print q_set
            request_result = provider.fill_data(q_set)
            # print request_result
            # headers = (u"")
            # data = tiblib.Dataset()
            # data.dict = request_result
            # print data.csv
            # return HttpResponse(data.csv)
            return render_to_response('audit/acount.html', {'result': request_result, 'type':'receivables'})
        elif request_type == 'received':
            print 'received'
            provider = ReceivedProvider()
            q_set = provider.object_filter(request)
            request_result = provider.fill_data(q_set)
            return render_to_response('audit/acount.html', {'result': request_result, 'type':'received'})


def return_url(request):
    if request.method =="GET":
        host = request.META['HTTP_HOST']
        data = urllib.urlencode(request.GET)
        print data
        # req = urllib2.Request(url,data)
        url = '/audit/action/down_load_financial_report?'+data
        print url
        return HttpResponse(url)





