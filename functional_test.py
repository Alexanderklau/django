from selenium import webdriver
browser = webdriver.Firefox()
browser.get('Http://localhost:8000')
assert 'Django' in browser.title
