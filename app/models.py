from django.db import models

APNS_PLATFORM = 'apns'
GCM_PLATFORM = 'gcm'
ANDROID_PLATFORM = 'android'
PLATFORM_CHOICES = (
    (APNS_PLATFORM, 'Apple Push Notifications'),
    (GCM_PLATFORM, 'Google Cloud Messaging'),
    (ANDROID_PLATFORM, 'Android'),
)


class App(models.Model):
    """
    Model that contains information about the supported apps by the middleware.
    """
    platform = models.CharField(choices=PLATFORM_CHOICES, max_length=10)
    app_id = models.CharField(max_length=255)

    push_key = models.CharField(max_length=255)
    logentries_token = models.CharField(max_length=255, blank=False, null=False, default='')
    partner_logentries_token = models.CharField(max_length=255, blank=True, null=True, default='')

    def __str__(self):
        return '{0} for {1}'.format(self.app_id, self.platform)

    class Meta:
        unique_together = ('app_id', 'platform')


class Device(models.Model):
    """
    Model for all device who register at the middleware.
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    sip_user_id = models.CharField(max_length=255, unique=True, primary_key=True)
    os_version = models.CharField(max_length=255, blank=True, null=True)
    client_version = models.CharField(max_length=255, blank=True, null=True)
    token = models.CharField(max_length=250)
    sandbox = models.BooleanField(default=False)
    last_seen = models.DateTimeField(blank=True, null=True)
    app = models.ForeignKey(App)
    remote_logging_id = models.CharField(max_length=255, blank=True, null=True)
    use_apns2 = models.BooleanField(default=False)

    def __str__(self):
        return '{0} - {1}'.format(self.sip_user_id, self.name)


class ResponseLog(models.Model):
    """
    Model for logging info about the device response.
    """
    platform = models.CharField(choices=PLATFORM_CHOICES, max_length=10)
    roundtrip_time = models.FloatField()
    available = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
