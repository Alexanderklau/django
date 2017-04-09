# -*- coding:utf8 -*-
#TODO: change them to submodule !!
#from business_manager.rc_server.rc_client import RCClient
from business_manager.message_server.message_client import MessageClient
from business_manager.bank_server.bank_server.bank_client import BankClient

from business_manager.order_management_server.order_management_client import OrderClient
from business_manager.user_center.user_center_client import UserCenterClient
#from gearman import GearmanClient

from django.conf import settings
import redis
import pymongo
from business_manager.python_common.log_client import CommonLog as Log
import hashlib
import datetime
from business_manager.business_data.business_data_report_client import BusinessDataReportClient

message_client = MessageClient(settings.MESSAGE_SERVER["HOST"], settings.MESSAGE_SERVER["PORT"],logger = None)
risk_client = OrderClient(settings.RISK_SERVER["HOST"], settings.RISK_SERVER["PORT"])
bank_client = BankClient(settings.BANK_SERVER["HOST"], settings.BANK_SERVER["PORT"], None, 60000)
user_center_client = UserCenterClient(settings.USER_CENTER_SERVER['HOST'], settings.USER_CENTER_SERVER['PORT'])
data_report_redis = redis.StrictRedis(host = settings.DATA_REPORT_SERVER['REDIS'], port = settings.DATA_REPORT_SERVER['REDIS_PORT'],
                                     password = settings.DATA_REPORT_SERVER['REDIS_AUTH'], db = settings.DATA_REPORT_SERVER['REDIS_DB'])
data_report_client = BusinessDataReportClient(settings.DATA_REPORT_SERVER['HOST'], settings.DATA_REPORT_SERVER['PORT'], data_report_redis, Log())

redis_client = redis.StrictRedis(host=settings.REDIS["HOST"], port=settings.REDIS["PORT"], password=settings.REDIS["AUTH"],db=0)
if settings.MONGO["USER"]:
    mongo_uri = 'mongodb://%s:%s@%s:%d/%s' % (settings.MONGO["USER"], settings.MONGO["AUTH"],
                                          settings.MONGO["HOST"], settings.MONGO["PORT"],
                                          settings.MONGO["DB"])
else:
    mongo_uri = 'mongodb://%s:%d/%s' % (settings.MONGO["HOST"], settings.MONGO["PORT"],
                                          settings.MONGO["DB"])
mongo_client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=30000)
