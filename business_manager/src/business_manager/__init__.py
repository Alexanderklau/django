from __future__ import absolute_import

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
# from celery import app as celery_app  # noqa

from django.conf import settings
import sys, os
sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0], 'business_manager'))
#RedisClient()

import threading

def test():
    print "I was at the"
    import schedule
    import time
    def job():
        print("I'm working...")

    schedule.every(1).minutes.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)

#t1 = threading.Thread(target=test)
#t1.setDaemon(True)
#t1.start()
