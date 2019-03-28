import flask_wtf, wtforms

class AuthorizeForm(flask_wtf.FlaskForm):
    authorize = wtforms.SubmitField("Authorize")
