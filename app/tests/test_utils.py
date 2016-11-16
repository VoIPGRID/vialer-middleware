import datetime

from django.test import TestCase

from ..models import ResponseLog, GCM_PLATFORM
from ..utils import get_metrics


class GetMetricsTestCase(TestCase):
    """
    Test for the get_metrics utils function.
    """
    def setUp(self):
        """
        Setup start and end date.
        """
        super(GetMetricsTestCase, self).setUp()

        self.first_of_month = datetime.date.today().replace(day=1)
        self.end_date = self.first_of_month.replace(day=3)

    def _create_entries(self, platform):
        """
        Create 4 entries for tests.
        """
        # Available logs.
        log1 = ResponseLog.objects.create(
            platform=platform,
            roundtrip_time=1.5,
            available=True,
        )
        log1.date = self.first_of_month
        log1.save()

        log2 = ResponseLog.objects.create(
            platform=platform,
            roundtrip_time=2,
            available=True,
        )
        log2.date = self.first_of_month.replace(day=2)
        log2.save()

        log3 = ResponseLog.objects.create(
            platform=platform,
            roundtrip_time=2.5,
            available=True,
        )
        log3.date = self.first_of_month.replace(day=3)
        log3.save()

        # Not available logs.
        log4 = ResponseLog.objects.create(
            platform=platform,
            roundtrip_time=4.0,
            available=False,
        )
        log4.date = self.first_of_month.replace(day=2)
        log4.save()

        log5 = ResponseLog.objects.create(
            platform=platform,
            roundtrip_time=6.0,
            available=False,
        )
        log5.date = self.first_of_month.replace(day=2)
        log5.save()

    def test_get_metrics(self):
        """
        Test for getting metrics for 1 platform.
        """
        self._create_entries(GCM_PLATFORM)

        metrics = get_metrics(self.first_of_month, self.end_date, GCM_PLATFORM)

        self.assertEquals(metrics['total_count'], 5)

        self.assertEquals(metrics['available']['count'], 3)
        self.assertEquals(metrics['available']['avg'], 2.0)
        self.assertEquals(metrics['available']['min'], 1.5)
        self.assertEquals(metrics['available']['max'], 2.5)

        self.assertEquals(metrics['not_available']['count'], 2)
        self.assertEquals(metrics['not_available']['avg'], 5.0)
        self.assertEquals(metrics['not_available']['min'], 4.0)
        self.assertEquals(metrics['not_available']['max'], 6.0)
