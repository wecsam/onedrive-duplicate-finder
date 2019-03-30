# OneDrive Duplicate File Finder

This is a simple application to find files that have the exact same contents in
the user's account on Microsoft OneDrive. It works by finding files that have
identical SHA-1 hashes.

## Dependency installation

This web app was built for Python 3.6 with the Flask microframework. To install
required libraries, run:

    pip install -r requirements.txt

## Configuration for development

These instructions are for Windows only. Instructions for other operating
systems may be added in the future.

First, create a secret key for Flask. This value is necessary for [Flask
sessions](http://flask.pocoo.org/docs/1.0/quickstart/#sessions) to work. A
string of 20 random characters should suffice; refer to the Flask documentation
for more information. Create a new file called `Test_Config.bat` and add the
following line:

    SET APP_SECRET_KEY={your key here}

Next, create a Microsoft Graph app. Follow the instructions [in the Microsoft
documentation](https://docs.microsoft.com/graph/auth-register-app-v2) to set
this up. Once you have your OAuth app ID and secret, add them to
`Test_Config.bat` like so:

	SET OAUTH_APP_ID={app ID}
	SET OAUTH_APP_SECRET={app secret}

There should be three lines total in this file: one for `APP_SECRET_KEY`, one
for `OAUTH_APP_ID`, and one for `OAUTH_APP_SECRET`.

## Running locally

Once you have finished the configuration instructions above, you can run this
app locally. On Windows, just execute `Test_Run.bat`. The server should start
listening at http://localhost:5000/.

## Configuration for production

If you are setting up a server for production use, you may instead set the
`APP_SECRET_KEY`, `OAUTH_APP_ID`, and `OAUTH_APP_SECRET` environment variables
in the system configuration. You should also set the `OAUTH_CALLBACK`
environment variable to the URL in this application that the OAuth flow should
use as the callback URL.
