from django.conf.urls import patterns, include, url

try:
    from djcelery.views import apply
    urlpatterns = patterns('',
        url(r'^apply/(?P<task_name>.+?)/', apply, name='celery-apply'),
        url(r'^celery/', include('djcelery.urls')),
    )
except ImportError:
    urlpatterns = patterns('')
