from selenium import webdriver
import unittest

class VisitorTest(unittest.TestCase):
    def setUp(self):
        self.browser = webdriver.Firefox()
    def tearDown(self):
        self.browser.quit()
    def test_it_later(self):
        self.browser.get('htp://localhost:8000')
        self.assertIn('hello',self.browser.title)
        self.fail('Finish the test')

if __name__ == '__main__':
    unittest.main(warnings='ignore')