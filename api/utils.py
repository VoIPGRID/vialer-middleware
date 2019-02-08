from main.prometheus.consts import (
    APP_VERSION_KEY,
    CONNECTION_TYPE_KEY,
    DIRECTION_KEY,
    NETWORK_KEY,
    NETWORK_OPERATOR_KEY,
    OS_KEY,
    OS_VERSION_KEY,
)


def get_metrics_base_data(json_data):
    """
    Function to parse the base metric data from JSON into a new dict.

    Args:
        json_data (dict): JSON dict containing the data from the app.

    Returns:
        dict: Dict in the format we can store in Redis.
    """
    metrics_dict = {
        APP_VERSION_KEY: json_data.get(APP_VERSION_KEY),
        CONNECTION_TYPE_KEY: json_data.get(CONNECTION_TYPE_KEY),
        DIRECTION_KEY: json_data.get(DIRECTION_KEY),
        NETWORK_KEY: json_data.get(NETWORK_KEY),
        OS_KEY: json_data.get(OS_KEY),
        OS_VERSION_KEY: json_data.get(OS_VERSION_KEY),
    }

    if json_data.get(NETWORK_KEY, '').lower() != 'wifi':
        metrics_dict[NETWORK_OPERATOR_KEY] = json_data.get(NETWORK_OPERATOR_KEY)

    return metrics_dict
