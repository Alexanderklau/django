from django.conf.urls import patterns, url

from business_manager.wechat_notify import views


urlpatterns = patterns(
    'business_manager.import',
    url('^transfer_apply/', views.wechat_get_recently_applys),
)
