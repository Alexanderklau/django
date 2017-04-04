from django.shortcuts import render
import logging
from django.conf import settings
logger = logging.getLogger('views_test')

def global_setting(requests):
    return {'SITE_NAME':settings.SITE_NAME,
            'SITE_DESC':settings.SITE_DESC,
            }
def index(request):
    try:
        open('12312.txt','r')
        site_name = settings.SITE_NAME
    except Exception as e:
        logging.error(e)
    return render(request,'index.html',locals())
# Create your views here.
