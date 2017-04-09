# -*- coding: utf-8 -*-

from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.review.general_views import *
from business_manager.review.data_views import get_my_review_datatable, get_all_review_datatable
from business_manager.review.report_views import *
from business_manager.review.get_big_data_view import get_big_data_report
from business_manager.review import views

urlpatterns = patterns('business_manager.review',
   ## page view
   # (r'^$', get_dashboard_data),
   (r'^$',  RedirectView.as_view(url='/review/mine')),
   # (r'^rst$', login_required(get_rst)),
   (r'status/$', login_required(views.get_review_status)),
   (r'all_orders/$', login_required(views.all_review_orders)),
   (r'my_orders/$', login_required(views.my_review_orders)),
   (r'^manager$', get_manager_overview_html),
   (r'^employee$', get_employee_overview_html),
   (r'^client/(?P<client_type>good|overdue)$', get_client),
   (r'^info/employee$', get_review_employee),
   (r'^test$', login_required(change_employee_status)),


   #modal
   (r'^info/(?P<apply_id>\d+)$', get_review_info_view),   # 我的审批基本信息页面
   #(r'^info/promote/(?P<apply_id>\d+)$', login_required(get_review_promote_info_view)), # 审批额度提升页面
   #(r'^info/loan/(?P<apply_id>\d+)$', login_required(get_review_loan_info_view)),   # 审批二次提现
   (r'^info/view/(?P<apply_id>\d+)$', login_required(get_review_view)),   # 查看基本信息页面
   #(r'^info/view/(?P<apply_id>\d+)$', get_review_view),   # 查看基本信息页面
   #(r'^info/report/(?P<apply_id>\d+)$', login_required(get_review_report_info_view)),   # 上传外访报告信息
   (r'^info/contact/(?P<apply_id>\d+)$', login_required(get_review_contact_info_view)),   # 审批基本联系人信息
   #(r'^info/view/promote/(?P<apply_id>\d+)$', login_required(view_promote_info_view)),# 查看额度提升页面
   #(r'^info/view/loan/(?P<apply_id>\d+)$', login_required(view_loan_info_view)),# 查看二次提现
   (r'^info/backletter/(?P<apply_id>\d+)$', login_required(show_backletter)),# 查看保函
    # 请求三方窗口
   (r'^info/report/(?P<apply_id>\d+)$', login_required(get_report_page)),# 返回report结果
   (r'^info/repay_plant/(?P<apply_id>\d+)$', login_required(show_repay_plant)),# 查看还款计划
   (r'^info/protocol/(?P<apply_id>\d+)$', login_required(show_protocol_report)),# 查看信用咨询及管理服务协议
   (r'^info/safeguard/', login_required(show_safeguard_report)),# 查看委托保证合同
    # 请求

    #获取审批页面信息+上传资料信息
   (r'^upload_info', upload_info),
   (r'^get_apply_info', get_apply_info),




   ## review action
   (r'^action/change_employee_status', change_employee_status),
   (r'^action/add/$', add_review),
   (r'^action/add$', add_review),
   (r'^action/cancel', cancel_review),
   (r'^action/promotion', finish_promotion_review),
   (r'^action/loan', finish_loan_review),
   (r'^action/re_apply_add_review', re_apply_add_review),

   (r'^action/finish', finish_review),
   (r'^action/reset_review', reset_review),
   (r'^action/upload_report', upload_report),
   (r'^action/download_others_report/(?P<apply_id>\d+)$', donwload_report),
   #(r'^action/start', login_required(start_review)),
   #(r'^action/end', login_required(end_review)),

   ## get json data for DataTables
   (r'^my_review_json$', login_required(get_my_review_datatable)),
   (r'^all_review_json$', login_required(get_all_review_datatable)),

   ## download file
   (r'^get_call$', get_call),
   (r'^download_addressbook$', download_addressbook),
   (r'^download_review_table_1$', download_review_table_1),
   (r'^download_review_table_2$', download_review_table_3),
   #(r'^download_record$', download_record),


   (r'^get_big_data_report',get_big_data_report)



)
