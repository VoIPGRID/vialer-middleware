import re

from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.views.static import serve


urlpatterns = [
    url(r'^api/', include('api.urls')),
    url(r'^admin/', include(admin.site.urls)),

    # XXX: Hack for static files, gunicorn can't serve them.
    #      django explicitly states that using the staticfiles_urlpatterns,
    #      is *not* suitable for production. But as this is only used for
    #      admin interface we use it anyway.
    #      This has been copied from: django.conf.urls.static
    url(r'^%s(?P<path>.*)$' % re.escape(settings.STATIC_URL.lstrip('/')), serve,
        kwargs={'document_root': settings.STATIC_ROOT}),
]
