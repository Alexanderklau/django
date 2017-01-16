from django.test import TestCase
from django.core.urlresolvers import resolve
from Test.views import home_page
from django.http import HttpRequest
# Create your tests here.
class HomePage(TestCase):
    def test_root_url_home_Page(self):
        found = resolve('/')
        self.assertEqual(found.func,home_page)

    def test_home_page_correct(self):
        requset = HttpRequest()
        response = home_page(requset)
        self.assertTrue(response.content.startswith(b'<html>'))
        self.assertIn(b'<title>Hello word!</title>',response.content)
        self.assertTrue(response.content.endswith(b'</html>'))

