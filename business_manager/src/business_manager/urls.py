#from django.contrib.auth.views import login, logout, password_change
from django.contrib.auth.views import logout, password_change
from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import RedirectView
from business_manager.employee.views import login, change_password
admin.autodiscover()

from business_manager.util import common_view


urlpatterns = patterns('',

    #url(r'^$', 'business_manager.user.getViewByUser'),
    url(r'^$',  RedirectView.as_view(url='index.html')),
    url(r'^order/', include('business_manager.order.urls')),
    url(r'^review/', include('business_manager.review.urls')),
    url(r'^operation/', include('business_manager.operation.urls')),
    url(r'^collection/', include('business_manager.collection.urls')),
    url(r'^custom/', include('business_manager.custom.urls')),
    url(r'^audit/', include('business_manager.audit.urls')),
    url(r'^fake/', include('business_manager.fake.urls')),
    url(r'new_order/', include('business_manager.new_order.urls')),
    url(r'pc_reg/', include('business_manager.pc_reg.urls')),
    url(r'config_center/', include('business_manager.config_center.urls')),
    url(r'employee/', include('business_manager.employee.urls')),

    url(r'^import/', include('business_manager.import_data.urls')),
    url(r'^', include('business_manager.strategy.urls')),
    url(r'^wechat_notify/', include('business_manager.wechat_notify.urls')),

    ## other pages
    (r'^thanks', TemplateView.as_view(template_name='common/404.html')),
    (r'^help', TemplateView.as_view(template_name='common/404.html')),
    (r'^feedback', TemplateView.as_view(template_name='common/404.html')),

    ## admin
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    ## account
    url(r'^accounts/login/$',  login),
    url(r'^accounts/change_password/$', change_password),
    url(r'^accounts/logged_out/$', logout, {'next_page': '/accounts/login'}),
    # url(r'^accounts/change_password/$', password_change, {'post_change_redirect':'/'}),
) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



#if settings.DEBUG:
#    import debug_toolbar
#    urlpatterns += patterns('',
#        url(r'^__debug__/', include(debug_toolbar.urls)),
#    )

handler403 = common_view.forbidden_view
