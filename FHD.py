# -*- coding: utf-8 -*-

from datetime import datetime
import flask
from flask_sqlalchemy import SQLAlchemy
import requests
import random

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

from config.config import Config


app = flask.Flask(__name__)
app.config.from_pyfile(app.root_path + '/config/app.cfg', silent=True)
config = Config()
config.set_config(app)


# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = app.root_path + "/client_secret.json"


# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = app.config['OAUTH_SCOPES']
# SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read',
#           'https://www.googleapis.com/auth/fitness.activity.write',
#           'profile', 'email',
#           'https://www.googleapis.com/auth/user.birthday.read',
#           'https://www.googleapis.com/auth/user.phonenumbers.read']



# Create DB/Tables if they do not exist.
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), index=True, unique=True, nullable=False)
    fname = db.Column(db.String(100), nullable=True)
    lname = db.Column(db.String(100), nullable=True)
    avatar = db.Column(db.String(200))
    # dob = db.Column(db.Date(), nullable=True)
    active = db.Column(db.Boolean, default=False)
    tokens = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow())


# class Badges(db.Model):
#     __tablename__ = "badges"
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), nullable=False)
#     description = db.Column(db.String(200), nullable=False)
#     icon_url = db.Column(db.String(200), nullable=False)
#     active = db.Column(db.Boolean, default=False)

db.create_all()


@app.route('/')
def index():
    image = random.choice(['1', '2', '3', '4', '5'])
    index_image = flask.url_for('static', filename='img/{}.jpeg'.format(image))
    if 'credentials' in flask.session:
        return flask.render_template('dashboard.html', session=flask.session)
    else:
        return flask.render_template('index.html', index_image=index_image)


@app.route('/logout')
def logout():
    if 'credentials' in flask.session:
        del flask.session['credentials']
    return flask.redirect('/')


@app.route('/profile')
def test_api_request():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    # Save credentials back to session in case access token was refreshed.
    flask.session['credentials'] = credentials_to_dict(credentials)
    # Actually request user info
    service = googleapiclient.discovery.build('people', 'v1',
                                              credentials=credentials)
    result = service.people().get(resourceName='people/me',
                                  personFields='addresses,ageRanges,'
                                               'biographies,'
                                               'birthdays,braggingRights,'
                                               'coverPhotos,emailAddresses,'
                                               'events,genders,imClients,'
                                               'locales,memberships,metadata,'
                                               'names,nicknames,occupations,'
                                               'organizations,phoneNumbers,'
                                               'photos,relations,'
                                               'relationshipInterests,'
                                               'relationshipStatuses,'
                                               'residences,skills,'
                                               'taglines,urls').execute()

    email = result['emailAddresses'][0]['value']
    fname = result['names'][0]['givenName']
    lname = result['names'][0]['familyName']
    avatar = result['photos'][0]['url']
    # dob = result['birthdays'][0]['date']
    # dob = datetime(dob['year'], dob['month'], dob['day']).date()
    active = True
    tokens = flask.session['credentials']['token']
    if not User.query.filter_by(email=email).first():
        new_user = User(email=email, fname=fname, lname=lname,
                        avatar=avatar, active=active, tokens=tokens)
        db.session.add(new_user)
        db.session.commit()

    current_user = User.query.filter_by(email=email).first()

    print("\n".join(["{}: {}".format(x.id, x.email) for x in User.query.all()]))
    return flask.render_template('profile.html', current_user=current_user)
    # return flask.jsonify(**result)


@app.route('/authorize')
def authorize():
    # Create flow instance to manage the OAuth 2.0
    # Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    flask.session['credentials'] = credentials_to_dict(credentials)

    return flask.redirect(flask.url_for('index'))


@app.route('/revoke')
def revoke():
    if 'credentials' not in flask.session:
        return ('You need to <a href="/authorize">authorize</a> before ' +
                'testing the code to revoke credentials.')

    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

    _revoke = requests.post('https://accounts.google.com/o/oauth2/revoke',
                            params={'token': credentials.token},
                            headers={'content-type':
                                     'application/x-www-form-urlencoded'})

    status_code = getattr(_revoke, 'status_code')
    if status_code == 200:
        return 'Credentials successfully revoked.' + print_index_table()
    else:
        return 'An error occurred.' + print_index_table()


def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


def print_index_table():
    return (
        '<table>' +
        '<tr><td><a href="/test">Test an API request</a></td>' +
        '<td>Submit an API request and see a formatted JSON response. ' +
        '    Go through the authorization flow if there are no stored ' +
        '    credentials for the user.</td></tr>' +
        '<tr><td><a href="/authorize">Test the auth flow directly</a></td>' +
        '<td>Go directly to the authorization flow. If there are stored ' +
        '    credentials, you still might not be prompted to reauthorize ' +
        '    the application.</td></tr>' +
        '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
        '<td>Revoke the access token associated with the current user ' +
        '    session. After revoking credentials, if you go to the test ' +
        '    page, you should see an <code>invalid_grant</code> error.' +
        '</td></tr>' +
        '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
        '<td>Clear the access token currently stored in the user session. ' +
        '    After clearing the token, if you <a href="/test">test the ' +
        '    API request</a> again, you should go back to the auth flow.' +
        '</td></tr></table>')


if __name__ == '__main__':
    # Specify a hostname and port that are set as a valid redirect URI
    # for your API project in the Google API Console.
    app.run(host='0.0.0.0', port=5000, debug=True,
            ssl_context=(app.root_path + '/ssl.crt', app.root_path + '/ssl.key'))
