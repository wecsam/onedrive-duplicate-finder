@PUSHD %~dp0
@REM Use this script to test the app during development.
@REM See the README for configuration instructions.
@CALL Test_Config.bat
SET OAUTH_CALLBACK=http://localhost:5000/callback
SET OAUTHLIB_INSECURE_TRANSPORT=1
SET FLASK_APP=main
SET FLASK_ENV=development
flask run
@POPD
