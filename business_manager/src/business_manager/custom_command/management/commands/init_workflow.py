#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand
from business_manager.config_center.models import *

class Command(BaseCommand):
    def init_workflow(self, platform):
        ws = WorkStatus(name = u'其他审批状态一', status_code = 's1', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态二', status_code = 's2', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态三', status_code = 's3', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态四', status_code = 's4', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态五', status_code = 's5', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态六', status_code = 's6', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态七', status_code = 's7', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态八', status_code = 's8', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()
        ws = WorkStatus(name = u'其他审批状态九', status_code = 's9', is_delete = 0, is_start = 0, is_end = 0, is_inner = 1, platform = platform)
        ws.save()

    def handle(self, *args, **kwargs):
        if len(args) < 1:
            print 'need params: platform'
            return
        self.init_workflow(args[0])
