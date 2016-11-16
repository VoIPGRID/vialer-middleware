import datetime

from django.conf.urls import url
from django.contrib import admin
from django.shortcuts import render

from .models import App, Device, ResponseLog, APNS_PLATFORM, GCM_PLATFORM, ANDROID_PLATFORM
from .utils import get_metrics


class DeviceAdmin(admin.ModelAdmin):
    pass


class AppAdmin(admin.ModelAdmin):
    pass


class ResponseLogAdmin(admin.ModelAdmin):
    """
    Custom admin to introduce the metrics view.
    """

    def get_urls(self):
        """
        Override to add the metrics url to possible admin urls for responselog.
        """
        original_urls = super(ResponseLogAdmin, self).get_urls()

        metrics_view = getattr(self, 'view_metrics')

        new_urls = [
            url(regex=r'%s' % '^metrics/$',
                name='metrics',
                view=self.admin_site.admin_view(metrics_view)),
        ]
        return new_urls + original_urls

    def last_day_of_month(self, any_day):
        """
        Function to return the last day of the month.

        Args:
            any_date (date): Date of the month to determine to last day for.

        Returns:
            Date object with the last day of the month.
        """
        next_month = any_day.replace(day=28) + datetime.timedelta(days=4)
        return next_month - datetime.timedelta(days=next_month.day)

    def view_metrics(self, request, **kwargs):
        """
        View for getting metrics for the roundtrip times.
        """
        month = request.GET.get('month', None)
        year = request.GET.get('year', None)

        start_date = datetime.date.today().replace(day=1)
        if month and year:
            start_date = datetime.date(int(year), int(month), 1)

        end_date = self.last_day_of_month(start_date)

        context = {
            'metrics': [
                get_metrics(start_date, end_date, APNS_PLATFORM),
                get_metrics(start_date, end_date, GCM_PLATFORM),
                get_metrics(start_date, end_date, ANDROID_PLATFORM),
            ]
        }

        return render(request, 'app/metrics.html', context=context)


admin.site.register(Device, DeviceAdmin)
admin.site.register(App, AppAdmin)
admin.site.register(ResponseLog, ResponseLogAdmin)
