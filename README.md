# Incoming Call Notifier
The main purpose of the project is to provide a middle man between phone apps
and SIP servers to be able to deliver incoming calls.

## Concept
The concept of receiving incoming calls on phone apps can be divided into 2 parts.
These parts will be discussed next.

### Registering a phone app
When you want to receive incoming calls on a phone app, the app needs to
register at this service. The flow for registering a device goes like this:

 * App checks with an API what sip account is used by a user (optional);
 * App registers a sip account and a token used for push notifications at the service;
 * Service validates this sip account and user combination (optional);
 * Service stores the combination of sip account and push token in a database;

There is also an endpoint to delete the combination of sip account and token
from the database.

### Receiving an incoming call
The flow of receiving an incoming call requires control of all the elements
involving a sip call. This is how to handle a incoming call:

 * Your number is being called;
 * PBX finds a sip account that belongs to an app;
 * It will make a HTTP POST request to the service with the sip account and call info;
 * The PBX will continue it's normal dialplan while waiting for a response on the HTTP POST request;
 * The service will handle the HTTP POST of the PBX and do a database lookup it the sip account registered with the service;
 * If the service finds a match a push notification will be send to the token belonging to the sip account;
 * The service will go into a while loop for a pre-defined amount of seconds delaying the response to the PBX;
 * Every 100ms the service will do a cache hit to see if the device responded to the push notification;
 * The device receives the push notification and will start the sip app;
 * After the app started the app should perform a SIP registration at the sipproxy;
 * After a successfull registration it will make a HTTP POST to the service to confirm the device is ready;
 * The while loop will find a cache hit and responds to the waiting PBX that the device is ready for the call;
 * The PBX will call the sip account like any other account;
 * The incoming call is received on the app.

This flow assumes all goes well. There are situations where the app will not be able to respond in a timely manner
due to connectivity issues and will not be able to receive the incoming call.

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

## Roadmap
We have some improvements planned for the near future:

 * Replace spawning threads by Django channels workers to be more efficient with open connections.

## Production setup
A suggestion about how to run this project in production:

 * A database cluster of 3 or more machines with replication;
 * A redis cluster of 3 or more machines with 2 nodes per machine;
 * Stateless load-balanced webservers (2 or more) for handeling the API requests.

## Final note
Although this is a fully functional product for us do not expect this to be
the case for your situation. Our goal is to keep the source open so other
developers can learn from our approach and adapt our code to their needs or start
from scratch with the archticture and inner workings all planned out already.
