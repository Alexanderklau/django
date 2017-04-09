# -*- coding: utf-8 -*-

from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.audit.general_views import *
from business_manager.audit.data_views import *
from business_manager.audit.views import *
from business_manager.audit.report_view import show_financial_report, return_url

urlpatterns = patterns('business_manager.audit',
    (r'^(?P<path>receivable_status|received_status|check_repay_status)', get_status),
    (r'^receivables/$', login_required(get_receivables)),
    (r'^paid_in_bills/$', login_required(get_paid_in_bills)),
    (r'^check_repay_bills/$', login_required(get_check_repay_bills)),
    (r'^check_repay_info/(?P<id>\d+)', login_required(get_check_repay_info)),
    (r'^confirm_check/$', login_required(confirm_check)),
    (r'^back_check/$', login_required(back_check)),
    (r'^(?P<path>down_check_repay_bills|down_paid_in_bills|down_receivables)', login_required(down_tables)),
    ## page view
    (r'^$',  RedirectView.as_view(url='/audit/check')),
    (r'^check$', login_required(get_check_page_view)),
    (r'^receivables$', login_required(get_receivables_page_view)),
    (r'^received$', login_required(get_received_page_view)),

    ## modal
    (r'^info/check/(?P<apply_id>\d+)$', login_required(get_check_modal_view)),     #复核页面

    ## action
    (r'^action/do_confirm_check', confirm_check),
    (r'^action/do_back_check', back_check),
    (r'^action/down_load_financial_report', show_financial_report),
    (r'^action/get_url', return_url),
    
    ## TODO:fixit
    (r'^download/check_table$', login_required(download_check_table)),
    (r'^table1$', login_required(get_table1_view)),
    (r'^table2$', login_required(get_table2_view)),
    (r'^table3$', login_required(get_table3_view)),

    (r'^download_receivable_table', login_required(download_receivable_table)),
    (r'^download_received_table', login_required(download_received_table)),

    #(r'^download_collection_table_1$', download_collection_table_1),

    ## get json data for DataTables
    (r'^check_repay_json$', login_required(get_check_datatable)),
    (r"^receivables_json$", login_required(get_receivables_datatable)),
    (r"^received_json$", login_required(get_received_datatable)),
    #(r'^all_collection_json$', login_required(get_all_collection_datatable)),

    #(r'^get_collection_record_json$', login_required(get_collection_record_data)),
)
