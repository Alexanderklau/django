# -*- coding: utf-8 -*-

from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.operation.general_views import *
from business_manager.operation.data_views import (get_pay_loan_datatable, get_repay_loan_datatable,get_table1_datatable,
                                                   get_table2_datatable,get_table3_datatable,get_table4_datatable,
                                                   dispatch_button, hand_dispatch)
from business_manager.operation.views import *

urlpatterns = patterns('business_manager.operation',
   ## new url
   (r'^comfirm_pay_status/$', login_required(comfirm_pay_status)),
   (r'(?P<uri>withhold_status|paid_status)', withhold_status),
   (r'^withhold_orders/$', login_required(withhold_orders)),
   (r'^withhold_order_list/$', login_required(get_withhold_orders)),
   (r'^do_repay_loan_batch/$', login_required(batch_repay_loan)),
   (r'^paid_orders/$', login_required(paid_orders)),
   (r'^pay_modal/(?P<pk>\d+)/$', login_required(pay_modal_info)),
   (r'^do_pay_loan/$', login_required(do_realtime_pay_action)),
   (r'^do_pay_loan_batch/$', login_required(do_realtime_pay_action_batch)),
   (r'^paid_order_list/$', login_required(get_paid_orders)),
   ## page view
   (r'^$',  RedirectView.as_view(url='/operation/repay')),
   (r'^pay$', login_required(get_pay_loan_view)),
   (r'^repay$', login_required(get_repay_loan_view)),
   (r'^repay4custom$', login_required(get_repay_loan_view4custom)),
   (r'^pay_modal/(?P<apply_id>\d+)$', (get_pay_modal_view)),
   (r'^repay_modal/(?P<apply_id>\d+)$', (get_repay_modal_view)),
   (r'^repay_modal4custom/(?P<apply_id>\d+)$', (get_repay_modal_view4custom)),
   (r'mifan_confirm_idlist$', (mifan_confirm_idlist)),
   (r'mifan_confirm_account', (get_mifan_confirm_account_view)),
   (r'mifan_confirm', (get_mifan_confirm_view)),
   (r'^table1$', login_required(get_table1_view)),
   (r'^table2$', login_required(get_table2_view)),
   (r'^table3$', login_required(get_table3_view)),
   (r'^table4$', login_required(get_table4_view)),
   (r'table3_result', login_required(get_table3_result_view)),
   ## action
   (r'download_pay_loan$', download_pay_loan),
   (r'export_repay_loan_table$', export_repay_loan_table),
   (r'export_pay_loan_table$', export_pay_loan_table),
   (r'download_table1', download_table1),
   (r'download_table2', download_table2),
   (r'download_table3', download_table3),
   (r'download_table4', download_table4),
   (r'^do_pay_loan$', do_realtime_pay_action),
   (r'^do_pay_loan_batch$', do_realtime_pay_action_batch),
   (r'^do_repay_loan$', new_do_realtime_repay_action),
   (r'add_collection_record$', add_collection_record),

   ## get json data for DataTables
   (r'^pay_loan_json$', login_required(get_pay_loan_datatable)),
   (r'^repay_loan_json$', login_required(get_repay_loan_datatable)),

   (r'^table1_json$', login_required(get_table1_datatable)),
   (r'^table2_json$', login_required(get_table2_datatable)),
   (r'table3_json', login_required(get_table3_datatable)),
   (r'table4_json', login_required(get_table4_datatable)),

   #(r'gen_excel$', gen_excel),

   (r'mifan_account_confirm_idlist', (mifan_account_confirm_idlist)),
   (r'^repay_batch_idlist', (repay_batch_idlist)),
   (r'^repay_modal_batch', (get_repay_modal_batch_view)),

   (r'test', (test)),
   (r'auto_pay_confirm', (auto_pay_confirm)),
   (r'auto_pay', (auto_pay)),

   (r'pre_repay_check_list', login_required(pre_repay_check_list)),

   (r'dispatch_button/', login_required(dispatch_button)),
   (r'dispatch/', login_required(hand_dispatch)),
)
