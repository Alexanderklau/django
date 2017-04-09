#!/usr/bin/env python
# coding=utf-8

from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required
from business_manager.config_center.general_views import *
from router import dispatcher

urlpatterns = patterns('business_manager.config_center',
                       #(r'^$', login_required(get_config_view)),
                       (r'^get_active_workflow', login_required(get_active_workflow)),

                       (r'^flow/add_field', login_required(add_field)),
                       (r'^model_experiment/create_experiment', login_required(create_experiment)),
                       (r'^model_experiment/delete_experiment', login_required(delete_experiment)),
                       (r'^model_experiment/add_model_to_experiment', login_required(add_model_to_experiment)),
                       (r'^model_experiment/del_model_from_experiment', login_required(del_model_from_experiment)),
                       (r'^model_experiment/modify_filter', login_required(modify_filter)),

                       (r'^add_field', login_required(add_field)),
                       (r'^delete_field', login_required(delete_field)),
                       (r'^update_field', login_required(update_field)),
                       (r'^get_fields', login_required(get_fields)),
                       (r'^search_field', login_required(search_field)),
                       (r'^searchfield_by_name', login_required(search_field_by_name)),
                       (r'^add_module', login_required(add_module)),
                       (r'^add_new_module_in', login_required(add_new_module_in)),
                       (r'^update_module', login_required(update_module)),
                       (r'^delete_module', login_required(delete_module)),
                       (r'^get_modules', login_required(get_modules)),
                       (r'^search_module_by_name', login_required(search_module_by_name)),
                       (r'^add_template', login_required(add_template)),
                       (r'^update_template', login_required(update_template)),
                       (r'^get_templates', login_required(get_templates)),
                       (r'^delete_template', login_required(delete_template)),
                       (r'^render_template', login_required(render_template)),
                       (r'^use_template', login_required(use_template)),
                       (r'^abandon_template', login_required(abandon_template)),
                       (r'^add_workflow', login_required(add_workflow)),
                       (r'^delete_workflow', login_required(delete_workflow)),
                       (r'^update_workflow', login_required(update_workflow)),
                       (r'^get_workflow', login_required(get_workflow)),
                       (r'^use_workflow', login_required(use_workflow)),
                       (r'^abandon_workflow', login_required(abandon_workflow)),
                       (r'^add_workstatus', login_required(add_workstatus)),
                       (r'^delete_workstatus', login_required(delete_workstatus)),
                       (r'^update_workstatus', login_required(update_workstatus)),
                       (r'^get_workstatus', login_required(get_workstatus)),
                       (r'^add_statusflow', login_required(add_statusflow)),
                       (r'^get_statusflow', login_required(get_statusflow)),
                       (r'^config_module/get_modules_from_system_name', login_required(get_modules_from_system_name)),
                       (r'^call_pass_line', login_required(call_pass_line)),
                       (r'^get_product_list', login_required(get_product_list)),
                       # (r'^', abandon_template),
                      )
