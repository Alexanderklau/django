from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
import json

@csrf_exempt
def get_big_data_report(requst):
    if requst.method == 'GET':
        user_id = requst.GET.get('user_id')
        rsp = requests.post(settings.DATA_SERVER['URL'] + 'get_token', data= json.dumps({'user_id':user_id, 'org_account':settings.DATA_SERVER['ORG_NAME'], 'service_id': settings.DATA_SERVER['SERVICE_ID']}))
        return HttpResponse(json.loads(rsp.content).get('data'))
