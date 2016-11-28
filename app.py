import os
import logging
from datetime import datetime, timedelta

import requests
from flask import Flask, request, session, url_for
app = Flask(__name__)
app.config['secret_key'] = os.environ['FLASK_SECRET_KEY']

logging.basicConfig(level='DEBUG')

GITLAB_HOST = os.environ['GITLAB_HOST']
GITLAB_APPID = os.environ['GITLAB_APPID']
GITLAB_APP_SECRET = os.environ['GITLAB_APP_SECRET']


@app.route('/')
def hello_world():
    logging.debug('hello world')
    return 'Hello, World!'


@app.route('/auth')
def auth():
    code = request.args.get('code')

    url = GITLAB_HOST + '/oauth/token'
    params = {
        "client_id": GITLAB_APPID,
        "client_secret": GITLAB_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": url_for('.auth', _external=True)
    }

    r = requests.post(url, params=params)
    logging.debug('result:', url, params, r.content, r.status_code)
    if r.status_code != 200:
        return r.content, 400
    data = r.json()
    session['access_token'] = data['access_token']
    session['expires_at'] = datetime.now() + timedelta(seconds=data['expires_in'])
    session['refresh_token'] = data['refresh_token']

    return "ok"


@app.route("/token")
def token():
    return "ok"
