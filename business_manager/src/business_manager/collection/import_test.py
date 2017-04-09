from django.test import TestCase
#encoding: utf-8

import sys, os, json
#sys.path.append('gen-py')
sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0], '../gen-py'))

import random
import base64
import unittest
import httplib
import urllib2

class CollectionImportTestCase(unittest.TestCase):
    _base_request = u' \
    {\
        "all_collection_data_length": "2",\
        "channel" : "9f",\
        "actual_collection_data": [\
            {\
                "user_info": {\
                    "user_id": "test_id",\
                    "name": "name123",\
                    "phone_no": "13912341234",\
                    "id_no": "430202198711032018",\
                    "relative_list": [\
                        {\
                            "name": "某某",\
                            "relation_ship": "1",\
                            "address_name": "通讯录名字",\
                            "tel": "xxxxxx"\
                        },\
                        {\
                            "name": "某某2",\
                            "relation_ship": "2",\
                            "address_name": "通讯录名字",\
                            "tel": "xxxxxxyyy"\
                        }\
                    ]\
                },\
                "repayment_info": {\
                    "repayment_id": "123",\
                    "amount": "10000",\
                    "apply_time": "2013-10-10 23:40:00",\
                    "pay_time": "2013-10-10 23:40:00"\
                },\
                "strategy_id": "xxxxx"\
            }\
        ]\
    }\
    '

    def generate_collection_info(request):
        return HttpResponse(resp)

    def setUp(self):
        pass

    def test_1(self):
        try:
            httpClient = httplib.HTTPConnection("127.0.0.1", 8000, timeout=30)
            headers = {"Content-type": "application/json"}
            httpClient.request("POST", "/collection/import_collection_info", self._base_request.encode('utf-8'), headers)
            response = httpClient.getresponse()
            resp = response.read()
            print resp
            self.assertEqual(response.status, 200)
        except Exception, e:
            print e
        finally:
            if httpClient:
                httpClient.close()

if __name__ == '__main__':
    unittest.main()
