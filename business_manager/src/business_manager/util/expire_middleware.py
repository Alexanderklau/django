# -*- coding:utf-8 -*-
from datetime import datetime

from django.conf import settings
from django.http import HttpResponseRedirect
from django.contrib.auth import logout


class ExpireMiddleware(object):

    def process_request(self, request):
        last_activity_time = request.session.get('last_activity_time')
        now = datetime.now()
        if not last_activity_time:
            request.session['last_activity_time'] = now.strftime('%Y-%m-%d %H:%M:%S')
            return
        record_datetime = datetime.strptime(last_activity_time, '%Y-%m-%d %H:%M:%S')
        if (now - record_datetime).seconds > settings.NO_ACTIVITY_EXPIRE_TIME:
            logout(request)
            print(' %s last activity_time: %s, current time: %s' % (request.user, record_datetime, now))
            # return HttpResponseRedirect('http://coimport.rongshutong.com/static/SaasWeb/login.html')
            return HttpResponseRedirect('/static/SaasWeb/login.html')
        else:
            print('no expired %s last activity_time: %s, current time: %s' % (request.user, record_datetime, now))
            request.session['last_activity_time'] = now.strftime('%Y-%m-%d %H:%M:%S')
