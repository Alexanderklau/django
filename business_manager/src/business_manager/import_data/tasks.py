# -*- coding:utf-8 -*-
from __future__ import absolute_import

from business_manager.import_data.parse_file import parse_file
from business_manager.celery import app


@app.task
def process_parse_file(record_id, platform):
    parse_file(record_id, platform)
