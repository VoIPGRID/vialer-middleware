# Docs
This file contains globale information about the project.

## ci.sh
This script is ran by our Jenkins CI server to run automated tests. It runs
all tests and checks if any violations where introduced in the codestyle. Code
coverage is also checked.

## Push services
The service relies heavely on push notification services provided by Apple and Google.

### Apple
For sending push notifications to an Apple device there multiple options. At
the moment the native way of sending pushes is used for Apple devices. This
involves making requests to send a push notification to a device using a
certificate provided by Apple. In this case a special VoIP certificate is
used to ensure the highest priority for the notification to be send.

### Google
Google has 2 services for sending push notification, Google Cloud Messaging and Firebase.
Firebase is the suggested solution for new projects but the service supports both at the moment.
To be able to send notification you need an account and API key used for sending the notifications
to the devices.

## API
Entrypoints

### Authentication
2 Endpoints of the API require basic authentication. These headers will
be used to authenticate through an other API that holds the info about
sip accounts. During this authentication a check is performed to validate
whether the user who made the requests is the owner of the sip account.

The endpoint that the PBX machines talk to should be firewalled. Access on
this endpoint should only be possible for the IP range of your PBX machines.
There is no reason for any other client to be able to post to this endpoint.

The endpoint the phone responds to when answering to a incoming call checks if
the unique token posted belongs to a waiting incoming call. There is no basic
authentication here because evert ms counts when it comes to incoming calls.

### /api/incoming-call/ (POST)
Endpoint for the PBX machine. This endpoint should be firewalled! See above.

 * **sip_user_id (int)**: Account id of the voip account being called (required).
 * **phonenumber (string)**: Phonenumber of the caller (required).
 * **caller_id (string)**: Human readable caller id (optional).
 * **call_id (string)**: PK reference used for the call (optional).

### /api/call-response/ (POST)
Enpoint for a device to respond to accept a call after waking up.

 * **unique_key (string)**: Key that was given in the device push message as reference (required).
 * **message_start_time (float datetime)**: Time given in the device push message to time the roundtrip (required).
 * **available (boolean)**: Wether the device is available to accept the call (optional but default `True`).

### /api/gcm-device/ & /api/android-device/ & /api/apns-device/ (POST)
Endpoint for registering/updating a device (token).

This endpoint requires authentication through HTTP Basic auth.

 * **sip_user_id (int)**: Account id of the voip account to register (required).
 * **token (string)**: Push token to send messages (required).
 * **app (string)**: App identifier like `com.voipgrid.vialer` (required).
 * **name (string)**: Name of the device (optional).
 * **os_version (string)**: Version of the OS on the device (optional).
 * **client_version (string)**: Version of the app used (optional).
 * **sandbox (boolean)**: Wether this device is a sandbox/test environment device (optional but default `False`).

### /api/gcm-device/ & /api/android-device/ & /api/apns-device/ (DELETE)

This endpoint requires authentication through HTTP Basic auth.

 * **sip_user_id (int)**: Account id of the voip account of the device to delete (required).
 * **token (string)**: Push token of the device to delete (required).
 * **app (string)**: App identifier like `com.voipgrid.vialer` of the device to delete (required).

### /api/hangup-reason/
Endpoint for posting a reason why a device did not answer a call.

This endpoint requires authentication through HTTP Basic auth.

 * **sip_user_id (int)**: Account id of the voip account to register (required).
 * **unique_key (string)**: Key that was given in the device push message as reference (required).
 * **reason (string)**: The reason why a call was not answered (required).

### /api/log-metrics/
Endpoint to post metric data which can be used by prometheus.

This endpoint requires authentication through HTTP Basic auth.

 * **sip_user_id (int)**: Account id of the voip account to register (required).
 * **os (str)**: The OS of the app (optional).
 * **os_version (str)**: The version of the OS of the app (optional).
 * **app_version (str)**: The version of the app (optional).
 * **app_status (str)**: The status of the app (optional).
 * **middleware_unique_key (str)**: The unique key of the call in the middleware (optional).
 * **bluetooth_audio (str)**: Did the app use bluetooth audio (optional).
 * **bluetooth_device (str)**: Details of the bluetooth device (optional).
 * **network (str)**: The network that was used for the call (optional).
 * **network_operator (str)**: The operator of the network if WiFi was not used (optional).
 * **network_signal_strength (str)**: The strength of the network (optional).
 * **direction (str)**: Incoming or outgoing call (optional).
 * **connection_type (str)**: The type of the connection (optional).
 * **call_setup_successful (str)**: Check if the call was setup successfully (optional).
 * **client_country (str)**: The country of the client (optional).
 * **call_id (str)**: The asterisk call id (optional).
 * **log_id (str)**: The logentries id (optional).
 * **time_to_initial_response (str)**: Time to first response in milliseconds (optional).
 * **failed_reason (str)**: The reason why a call failed (optional).

## Production setup
A suggestion about how to run this project in production:

 * A database cluster of 3 or more machines with replication;
 * A redis cluster of 3 or more machines with 2 nodes per machine;
 * Stateless load-balanced webservers (2 or more) for handeling the API requests.
