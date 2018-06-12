from django.conf.urls import url
from rest_framework import routers

from .views import CallResponseView, DeviceView, HangupReasonView, IncomingCallView, LogMetricsView

router = routers.DefaultRouter()

urlpatterns = [
    url(r'^incoming-call/', IncomingCallView.as_view()),
    url(r'^call-response/', CallResponseView.as_view()),
    url(r'^hangup-reason/', HangupReasonView.as_view()),
    url(r'^log-metrics/', LogMetricsView.as_view()),
    url(r'^(?P<platform>(apns|gcm|android))-device/', DeviceView.as_view()),
]
