from rest_framework import serializers

from .validators import phone_number_validator, token_validator


class TokenSerializer(serializers.Serializer):
    """
    Base serializer for the token field.
    """
    token = serializers.CharField(max_length=250, validators=[token_validator])


class SipUserIdSerializer(serializers.Serializer):
    """
    Base serializer for the sip_user_id field.
    """
    sip_user_id = serializers.IntegerField(max_value=999999999, min_value=int(1e8))


class DeviceSerializer(TokenSerializer, SipUserIdSerializer):
    """
    Serializer for the device view post.
    """
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    os_version = serializers.CharField(max_length=255, allow_blank=True, required=False)
    client_version = serializers.CharField(max_length=255, allow_blank=True, required=False)
    app = serializers.CharField(max_length=255)
    sandbox = serializers.BooleanField(default=False)
    remote_logging_id = serializers.CharField(max_length=255, allow_blank=True, required=False)


class DeleteDeviceSerializer(TokenSerializer, SipUserIdSerializer):
    """
    Serializer for the device view delete.
    """
    app = serializers.CharField(max_length=255)


class CallResponseSerializer(serializers.Serializer):
    """
    Serializer for the call response view.
    """
    unique_key = serializers.CharField(max_length=255)
    message_start_time = serializers.FloatField()
    available = serializers.BooleanField(default=True)


class IncomingCallSerializer(SipUserIdSerializer):
    """
    Serializer for the incoming call view.
    """
    caller_id = serializers.CharField(max_length=255, default='', allow_blank=True)
    phonenumber = serializers.CharField(max_length=32, validators=[phone_number_validator])
    call_id = serializers.CharField(max_length=255, default=None, allow_blank=True)
