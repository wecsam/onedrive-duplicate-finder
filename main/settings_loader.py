import os, urllib.parse

settings = {}

def _load():
    '''
    Loads settings for this application into the `settings` global variable.
    '''
    REQUIRED_KEYS = (
        "APP_SECRET_KEY",
        "OAUTH_APP_ID",
        "OAUTH_APP_SECRET",
        "OAUTH_CALLBACK",
    )
    for key in REQUIRED_KEYS:
        value = os.environ.get(key, None)
        if key is None:
            raise KeyError(
                "The {!r} key was not found in the settings.".format(key)
            )
        settings[key] = value

def get_oauth_callback_path():
    '''
    Returns the path portion of the OAuth callback URL from the settings. For
    example, if the callback URL is http://localhost:5000/callback, then the
    result is /callback.
    
    This function also checks that the URL has an origin and a path. In the
    example above, an error would be raised if http://localhost:5000 wasn't
    there.
    '''
    parsed = urllib.parse.urlparse(settings["OAUTH_CALLBACK"])
    if parsed.scheme and parsed.netloc and parsed.path:
        return parsed.path
    raise ValueError("The OAuth callback URL must have an origin and path.")

_load()
