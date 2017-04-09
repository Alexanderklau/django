# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from TkManager.util.cron_functions import init_dayTable


class Command(BaseCommand):
    def handle(self, *args, **options):
        init_dayTable()

