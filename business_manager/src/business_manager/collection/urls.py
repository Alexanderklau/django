# -*- coding: utf-8 -*-

from django.conf.urls import patterns
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.collection.general_views import *
from business_manager.collection.data_views import *
from business_manager.collection.batch_import import *
from business_manager.collection import views
from business_manager.collection.report import report_call_action 
from business_manager.operation.general_views import new_do_realtime_repay_action
from business_manager.operation.views import batch_repay_loan

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'record', views.CollectionRecordViewSet)
router.register(r'quality_control', views.QualityControlList)


urlpatterns = patterns('business_manager.collection',
    # 前后端分离新接口
    (r'^collection_type/$', views.get_collection_type),     # 拉取逾期级别
    (r'^lending_channels/$', views.get_lending_channels),   # 拉取贷款渠道
    (r'^collection_personnel/$', views.get_collection_personnel),   # 拉取催收人员
    (r'^all_collection_json$', login_required(views.all_collection)),   # 所有催收列表
    (r'^my_collection_json$', login_required(views.my_collection)),     # 我的催收列表
    (r'^action/user_info/', login_required(views.get_user_info)),   # 分配时用户信息
    (r'^action/change$', login_required(views.order_allocation)),   # 分配催收订单
    (r'^info/(?P<apply_id>\d+)$', login_required(views.pull_collection_info)),    # 催收用户详情
    (r'^get_loan_data$', login_required(views.pull_loan_info)),    # 贷款信息
    (r'^action/add_collection_record$', login_required(views.add_record)),   # 添加催记
    (r'^get_collection_record_json$', login_required(views.pull_collection_record)),    # 拉取催记
    (r'^get_relation_info/$', login_required(views.get_relation_info)),     # 获取关系联系人信息 (需添加关系用户信息)
    (r'^add_or_update_relationship/$', login_required(views.add_or_update_relationship)),    # 更新或创建关系联系人信息
    (r'^down_tables$', login_required(views.down_tables)),      # 下载报表
    (r'^new_down_tables$', login_required(views.test_down_tables)),      # 下载报表
    (r'^get_message_template/$', views.get_msg_template),  # 拉取短信模板
    (r'^send_message/$', login_required(views.send_message)),   # 发送短信
    (r'^repay_type/$', views.pull_repay_type),    # 还款类型
    (r'^do_repay_loan/$', login_required(new_do_realtime_repay_action)),    # 扣款接口
    (r'^call_report/$', report_call_action),    # 通话上报
    (r'^report_log$', views.report_log),        # 通话日志
    (r'^do_repay_loan_batch/$', batch_repay_loan),
    ## page view
    (r'^$',  RedirectView.as_view(url='/collection/mine')),
    (r'^all$', login_required(get_all_collection_view)),
    (r'^mine$', login_required(get_mine_collection_view)),

    ##modal
    (r'^info/(?P<apply_id>\d+)$', login_required(get_collection_info)),     # 催收页面
    (r'^info/view/(?P<apply_id>\d+)$', login_required(get_collection_info_view)), # 催收展示页面改用系统页面
    (r'^modal/dispatch/(?P<apply_id>\d+)$', login_required(dispatch_collection_info_view)), # 催收展示页面改用系统页面
    (r'^modal/message/(?P<apply_id>\d+)$', login_required(get_message_info)), # 短信发送modal
    (r'^modal/reduction/(?P<apply_id>\d+)$', login_required(get_reduction_info)), #减免的modal

    ## review action
    (r'^action/add/', add_review),
    #(r'^action/cancel', cancel_review),
    (r'^action/change', change_reviewer),
    (r'^action/finish', finish_review),
    (r'^action/do_repay_loan', login_required(do_collection_action)),

    (r'^action/sendmessage', send_message),
    (r'^action/reduction', do_reduction),
    (r'^action/add_collection_record', add_record),
    (r'^action/fileupload', upload_file),

    (r'^action/wx_add_collection_record', views.wx_add_record),
    (r'^wx_search', views.wx_search),
    (r'^wx_apply_info', views.wx_apply_info),

    (r'^import_collection_info$', import_collection_info),
    (r'^update_collection_info$', update_collection_info),
    (r'^generate_collection_info$', generate_collection_info),
    ##
    (r'^download_collection_table_1$', download_collection_table_1),
    #(r'^download_collection_table_2$', download_collection_table_2),

    ## get json data for DataTables
    (r'^my_collection_json$', login_required(get_my_collection_datatable)),
    (r'^all_collection_json$', login_required(get_all_collection_datatable)),

    # (r'^get_collection_record_json$', login_required(get_collection_record_data)),


    (r'^import/address$', import_addressbook_info),
    (r'^import/callrecord$', import_callrecords_info),
    (r'^contact_post$', contact_post),
    (r'^get_employee_info$', login_required(get_employee_info)),
    (r'^download_bi_table', login_required(views.download_bi_table)),

    (r'^cn_group/$', login_required(views.CnGroupView.as_view())),
    (r'^inspection_result/$', login_required(views.InspectionResult.as_view())),
    (r'^inspection_analysis/$', login_required(views.InspectionAnalysis.as_view())),

    # 信修
    (r'^lost_contact/$', login_required(views.lost_contact)),      # 失联
    # (r'info_repair/$', login_required(views.)),
    (r'^info_repair/verify/$', login_required(views.verify_lost_order)),      # 信修核实
    (r'^info_repair/module/$', login_required(views.get_info_repair_module)),      # 信修模块
    (r'^info_repair/detail/$', login_required(views.info_repair_detail)),      # 信修详情
    (r'^info_repair/verify_field/$', login_required(views.verify_info_field)),      # 核实信修字段
    (r'^info_repair/history/$', login_required(views.info_repair_history)),      # 信修详情

    (r'^apply_status/$', login_required(views.apply_status)),      # 信修详情
    (r'^my_apply_status/$', login_required(views.my_apply_status)),      # 信修详情



) + router.urls
