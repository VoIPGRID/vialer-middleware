from django.db.models import Avg, Max, Min

from .models import ResponseLog


def get_metrics(start_date, end_date, platform):
    """
    Function to get a dict with metrics for the given date range and platform.

    Args:
        start_date (date): Start date to get metrics for.
        end_date (date): End date to get metrics for.
        platform (string): Platform to get metrics for.

    Returns:
        Dict containing the metrics.
    """
    def _get_min(query):
        return query.aggregate(Min('roundtrip_time'))['roundtrip_time__min']

    def _get_max(query):
        return query.aggregate(Max('roundtrip_time'))['roundtrip_time__max']

    def _get_avg(query):
        return query.aggregate(Avg('roundtrip_time'))['roundtrip_time__avg']

    base_query = ResponseLog.objects.filter(
        platform=platform, date__range=(start_date, end_date)).order_by('roundtrip_time')
    total_count = base_query.count()

    percentile = int(total_count * 0.95)

    available_query = base_query.filter(available=True)
    available_count = available_query.count()
    avg_available = _get_avg(available_query[:percentile])
    min_available = _get_min(available_query[:percentile])
    max_available = _get_max(available_query[:percentile])

    not_available_query = base_query.filter(available=False)
    not_available_count = not_available_query.count()
    avg_not_available = _get_avg(not_available_query[:percentile])
    min_not_available = _get_min(not_available_query[:percentile])
    max_not_available = _get_max(not_available_query[:percentile])

    results = {
        'platform': platform,
        'start_date': start_date,
        'end_date': end_date,
        'total_count': total_count,
        'available': {
            'count': available_count,
            'avg': avg_available,
            'min': min_available,
            'max': max_available,
        },
        'not_available': {
            'count': not_available_count,
            'avg': avg_not_available,
            'min': min_not_available,
            'max': max_not_available,
        },
    }

    return results
