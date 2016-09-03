from selenium import webdriver
import unittest

browser = webdriver.Firefox()
browser.get('http://localhost:8000')
assert 'Django' in browser.title
