import flask, json, oauthlib.oauth2, time
from . import app, file_tree, forms, onedrive, settings_loader

def get_scan():
    # Resume the previous scan under this access token.
    try:
        # Use the OneDrive access token as a unique token.
        scan = file_tree.DuplicateFileScan.load(
            onedrive.get_token(),
            onedrive.get_children,
            onedrive.get_folder_url
        )
    except file_tree.DuplicateFileScan.NoSuchSave:
        # There is no previous scan; start a new one.
        scan = file_tree.DuplicateFileScan(
            "sha1Hash" if onedrive.is_personal() else "quickXorHash",
            onedrive.get_children,
            onedrive.get_folder_url
        )
        scan.add_folder_url(onedrive.get_root_folder_url())
    return scan

@app.route(settings_loader.get_oauth_callback_path())
def handle_callback():
    # Handle an OAuth callback. Retrieve and store an access token.
    onedrive.handle_callback()
    flask.flash("You were successfully authorized.", "success")
    return flask.redirect(flask.url_for(".handle_root"))

@app.route("/", methods=("GET", "POST"))
def handle_root():
    authorize_form=forms.AuthorizeForm()
    # If the user initiated a sign-in, redirect to the OAuth authorization URL.
    if flask.request.method == "POST" and authorize_form.validate_on_submit():
        return flask.redirect(onedrive.get_authorization_url())
    # Display the form to prompt the user to initiate a sign-in. This extra
    # step helps to prevent the user from starting an OAuth authorization flow
    # by entering some URL accidentally.
    scan = None
    error = None
    error_api_url = None
    error_api_response = None
    if onedrive.is_authorized():
        try:
            scan = get_scan()
            # Scan for a certain amount of time and then return.
            # TODO: consider switching to do..while style
            time_start = time.time()
            while (time.time() - time_start) < 1.0:
                if scan.complete:
                    break
                try:
                    scan.step()
                except onedrive.APIKeyError as e:
                    error = "The API response could not be parsed because " \
                        "the {!r} key was missing.".format(e.args[0])
                    error_api_url = e.args[1]
                    error_api_response = e.args[2]
                if error:
                    break
        except oauthlib.oauth2.rfc6749.errors.TokenExpiredError:
            error = "Your session expired. " \
                "Please restart the scan by signing out and back in."
        # In an error condition, show the API response to the user.
        if error:
            try:
                error_api_response = json.dumps(error_api_response, indent=4)
            except:
                pass
        else:
            scan.save(onedrive.get_token())
    # Render the result.
    result = flask.Response(
        flask.render_template(
            "index.html",
            authorize_form=authorize_form,
            is_authorized=onedrive.is_authorized(),
            scan=scan,
            error=error,
            error_api_url=error_api_url,
            error_api_response=error_api_response
        )
    )
    # Refresh if the scan is not complete. We need to do this because the code
    # above only scans for a certain amount of time before returning, which may
    # happen before the scan is complete.
    if not error and scan and not scan.complete:
        result.headers["Refresh"] = "1"
    return result

@app.route("/logout")
def handle_logout():
    onedrive.deauthorize()
    flask.flash("You have been signed out.", "success")
    return flask.redirect(flask.url_for(".handle_root"))

@app.route("/results.json")
def handle_results_json():
    if onedrive.is_authorized():
        content = {"duplicates": list(get_scan().get_duplicates())}
        result = flask.Response(
            file_tree.JSONEncoder(indent=4).encode(content),
            mimetype="application/json"
        )
    else:
        result = flask.Response(
            '{"error": "unauthorized"}',
            mimetype="application/json",
            status=403
        )
    result.headers["Content-Disposition"] = "attachment"
    return result
