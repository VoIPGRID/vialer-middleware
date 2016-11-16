from django.conf.urls import url
from rest_framework import routers
from api.views import CallResponseView, DeviceView, IncomingCallView

router = routers.DefaultRouter()

urlpatterns = [
    url(r'^incoming-call/', IncomingCallView.as_view()),
    url(r'^call-response/', CallResponseView.as_view()),
    url(r'^(?P<platform>(apns|gcm|android))-device/', DeviceView.as_view()),
]
