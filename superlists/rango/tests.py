from django.test import TestCase
from django.core.urlresolvers import resolve
from rango.views import home_page

class HomePageTest(TestCase):
    def test_root_url_resolves_to_homr_page_view(self):
        found = resolve('/')
        self.assertEqual(found.func,home_page)
# Create your tests here.
