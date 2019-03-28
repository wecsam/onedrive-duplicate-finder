import flask, requests_oauthlib, urllib.parse
from . import file_tree, settings_loader

_OAUTH_AUTHORIZATION_URL = \
    "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_OAUTH_TOKEN_FETCH_URL = \
    "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_ORGANIZATION_PATH = "https://graph.microsoft.com/v1.0/organization"
_ONEDRIVE_PATH_ROOT = "https://graph.microsoft.com/v1.0/me/drive/root"
_ONEDRIVE_PATH_ITEMS = "https://graph.microsoft.com/v1.0/me/drive/items"
_ONEDRIVE_PATH_SUFFIX = \
    "/children?select=id,name,size,webUrl,parentReference,file,folder"

class NotAuthorized(Exception): pass

def _set_token(token):
    flask.session["oauth_token"] = token

def get_token():
    return flask.session.get("oauth_token")

def _pop_token():
    return flask.session.pop("oauth_token", None)

def _set_state(state):
    flask.session["oauth_state"] = state

def _pop_state():
    return flask.session.pop("oauth_state", None)

def _get_oauth_session():
    return requests_oauthlib.OAuth2Session(
        settings_loader.settings["OAUTH_APP_ID"],
        state=_pop_state(),
        token=get_token(),
        scope="User.Read Files.Read",
        redirect_uri=settings_loader.settings["OAUTH_CALLBACK"]
    )

def get_authorization_url():
    '''
    Returns the URL to which to redirect to start an OAuth flow.
    '''
    authorization_url, state = \
        _get_oauth_session().authorization_url(_OAUTH_AUTHORIZATION_URL)
    _set_state(state)
    return authorization_url

def handle_callback():
    '''
    Call this in the handler for the OAuth callback.
    '''
    _set_token(
        _get_oauth_session().fetch_token(
            _OAUTH_TOKEN_FETCH_URL,
            client_secret=settings_loader.settings["OAUTH_APP_SECRET"],
            authorization_response=flask.request.url
        )
    )

def is_authorized():
    return get_token() is not None

def deauthorize():
    _pop_token()

_last_result = None
_last_url = None

def _fetch_json(url):
    global _last_result, _last_url
    _last_url = url
    _last_result = _get_oauth_session().get(url).json()
    return _last_result

def get_last_url():
    return _last_url

def get_last_result():
    return _last_result

def is_personal():
    '''
    Returns True if the signed-in Microsoft user is a personal Microsoft
    account (e.g. Outlook.com, Hotmail.com, Live.com, MSN.com). Returns False
    if it is a OneDrive for Business account.
    '''
    api_response = _fetch_json(_ORGANIZATION_PATH)
    return not api_response.get("value", ())

def get_children(url, add_folder_url):
    '''
    Yields file_tree.Folder and file_tree.File objects that represent the
    contents of the given folder.
    
    Arguments:
        url:
            the full REST API URL that will list the children of a driveItem;
            see this link for more information:
            https://docs.microsoft.com/graph/api/driveitem-list-children
        add_folder_url:
            a function that takes one argument: another URL that later should
            be passed back to get_children()
    '''
    if not is_authorized():
        raise NotAuthorized
    api_response = _fetch_json(url)
    # Check for an error state.
    try:
        error_code = api_response["error"]["code"]
    except KeyError:
        pass
    else:
        if error_code == "itemNotFound":
            # This folder no longer exists.
            return
    # Iterate through the children.
    for child in api_response["value"]:
        id = child["id"]
        name = child["name"]
        size = child.get("size", 0)
        url = child["webUrl"]
        parent_id = child["parentReference"]["id"]
        parent_path = urllib.parse.unquote(child["parentReference"]["path"])
        folder = child.get("folder")
        if folder:
            # This is a folder.
            yield file_tree.Folder(
                id=id,
                name=name,
                size=size,
                url=url,
                parent_id=parent_id,
                parent_path=parent_path,
                child_count=folder["childCount"]
            )
        else:
            file = child.get("file")
            if file:
                # This is a file.
                hashes = file.get("hashes")
                if hashes is None:
                    hashes = {}
                yield file_tree.File(
                    id=id,
                    name=name,
                    size=size,
                    url=url,
                    parent_id=parent_id,
                    parent_path=parent_path,
                    mime_type=file.get("mimeType", ""),
                    hashes=hashes
                )
    # If there are more children on another page, pass the next page's URL.
    try:
        next_link = api_response["@odata.nextLink"]
    except KeyError:
        pass
    else:
        add_folder_url(next_link)

def get_root_folder_url():
    '''
    Returns the full URL that, when passed to get_children(), will result in
    the children in the root of the drive.
    '''
    return _ONEDRIVE_PATH_ROOT + _ONEDRIVE_PATH_SUFFIX

def get_folder_url(folder_id):
    '''
    Returns a full URL that, when passed to get_children(), will result in the
    children of the folder with the given folder ID.
    '''
    return "{}/{}{}".format(
        _ONEDRIVE_PATH_ITEMS,
        urllib.parse.quote(folder_id),
        _ONEDRIVE_PATH_SUFFIX
    )
