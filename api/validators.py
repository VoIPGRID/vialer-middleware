import re

from rest_framework import serializers


def token_validator(token):
    """
    Function to validate if a token is in the required format.

    Args:
        token (string): The APNS or GCM push token.

    Raises:
        ValidationError: When the token is not correctly formated.
    """
    if ' ' in token:
        raise serializers.ValidationError('No whitespace allowed in token.')


def phone_number_validator(phone_number):
    """
    Function to validate if a phone_number is in the required format.

    Args:
        phone_number (string): The APNS or GCM push token.

    Raises:
        ValidationError: When the phone_number is not correctly formated.
    """
    phone_number_stripped = re.sub(r'[\+\(\)– - x]', '', phone_number)

    if not phone_number_stripped.isdigit():
        raise serializers.ValidationError('Not a valid phone number.')
