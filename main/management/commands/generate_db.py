from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from app.models import App, ANDROID_PLATFORM, APNS_PLATFORM


class Command(BaseCommand):
    help = 'Fill the database with default test data'

    def handle(self, *args, **kwargs):
        User.objects.create_user(
            username='admin',
            password='password123',
            is_superuser=True,
            is_staff=True,
        )

        app_id = 'com.voipgrid.vialer'

        App.objects.create(
            platform=ANDROID_PLATFORM,
            app_id=app_id,
        )
        App.objects.create(
            platform=APNS_PLATFORM,
            app_id=app_id,
        )
