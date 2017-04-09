from django.test import RequestFactory, TestCase

from business_manager.employee.models import Employee
from business_manager.order.apply_models import Apply


class OperationTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_hand_dispatch(self):
        params = {
            "order_id_list": [12345, 12346],
            "collector_id_list": [11, 22],
            "collector_group_list": [12, 12]
        }
        res = self.client.get('/operation/hand_dispatch/', params)
        self.assertEqual(res.status_code, 200)

    def test_dive_collector(self):
        collector_id_list = [11, 22]
        collectors = Employee.objects.filter(id__in=collector_id_list)
        dive_info = Employee.dive_collector(collectors)
        print dive_info

    def test_dive_orders(self):
        order_id_list = [1234, 1235]
        orders = Apply.objects.filter(id__in=order_id_list)
        order_info = Apply.dive_orders(orders)
        print order_info
