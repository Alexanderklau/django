# -*- coding: utf-8 -*-
import json

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from business_manager.collection.models import QualityControlRecord


def create_test_data():
    """创建测试数据"""
    pass


class CollectionDataProviderTestCase(TestCase):
    """"""
    def setUp(self):
        pass


class QualityViewTest(APITestCase):

    get_url = '/collection/qa_control/'
    delete_url = '/collection/qa_control/{}/'
    ok_code = 0
    error_code = 1
    test_file = 'test.xlsx'

    def test_list(self):
        res = self.client.get(self.get_url)
        self.standard_test(res)
        data = json.loads(res.content)
        self.assertEqual(data['count'], len(data['data']))

    def test_create(self):
        with open(self.test_file, 'rb') as data:
            res = self.client.post(self.url, {'file': data}, format='multipart')
        self.standard_test(res)
        data = json.load(res.content)

    def test_delete(self):
        random_obj = QualityControlRecord.objects.order_by("?")[1]
        res = self.client.delete(self.delete_url.format(random_obj.id))
        self.standard_test(res)

    def standard_test(self, res):
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = json.loads(res.content)
        self.assertEqual(data['code'], self.ok_code)
