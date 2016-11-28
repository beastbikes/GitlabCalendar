import os
import logging
from datetime import datetime, timedelta

import requests
from flask import Flask, request, session
app = Flask(__name__)

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
        "grant_type": "AUTHORIZATION_CODE",
        "redirect_uri": ""
    }

    r = requests.get(url, params)
    data = r.json()
    logging.debug('result:', data)
    session['access_token'] = data['access_token']
    session['expires_at'] = datetime.now() + timedelta(seconds=data['expires_in'])
    session['refresh_token'] = data['refresh_token']

    return "ok"


@app.route("/token")
def token():
    return "ok"
