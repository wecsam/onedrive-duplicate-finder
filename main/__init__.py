#!/usr/bin/env python3
import flask, flask_wtf, humanfriendly, os

app = flask.Flask(__name__)

from . import settings_loader
app.secret_key = settings_loader.settings["APP_SECRET_KEY"]
app.jinja_env.filters.update(list=list)
app.jinja_env.globals.update(humanfriendly=humanfriendly)
csrf = flask_wtf.csrf.CSRFProtect(app)
from . import routes

# Suppress the warning that happens when the OAuth scope is changed.
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
