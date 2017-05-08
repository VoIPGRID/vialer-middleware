# Vialer Middleware

The main purpose of the project is to provide a middle man between phone apps
and SIP servers to be able to deliver incoming calls.

## Status

Active

Although this is a fully functional product for us do not expect this to be
the case for your situation. Our goal is to keep the source open so other
developers can learn from our approach and adapt our code to their needs or start
from scratch with the archticture and inner workings all planned out already.

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

## Usage
See docs for more info.

### Requirements

 * docker
 * docker-compose

### Installation

```
$ git clone git@github.com:VoIPGRID/vialer-middleware.git
$ cd vialer-middleware
$ touch .env
$ docker-compose build
```

### Running

```
$ docker-compose up
```

## Contributing

See the [CONTRIBUTING.md](CONTRIBUTING.md) file on how to contribute to this project.

## Contributors

See the [CONTRIBUTORS.md](CONTRIBUTORS.md) file for a list of contributors to the project.

## Roadmap

### Changelog

The changelog can be found in the [CHANGELOG.md](CHANGELOG.md) file.

### In progress

 * Multiple push notifications
 * Documentation
 * Sentry monitoring

### Future

 * Replace spawning threads by Django channels workers to be more efficient with open connections.

## Get in touch with a developer

If you want to report an issue see the [CONTRIBUTING.md](CONTRIBUTING.md) file for more info.

We will be happy to answer your other questions at opensource@wearespindle.com

## License

Vialer Middleware is made available under the MIT license. See the [LICENSE file](LICENSE) for more info.
