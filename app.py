import os
import logging
from datetime import datetime, timedelta

import requests
from flask import Flask, request, session, url_for, redirect, abort, jsonify


app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']


logging.basicConfig(level='DEBUG')

GITLAB_HOST = os.environ['GITLAB_HOST']
GITLAB_APPID = os.environ['GITLAB_APPID']
GITLAB_APP_SECRET = os.environ['GITLAB_APP_SECRET']


@app.errorhandler(401)
def not_login_handler(error):
    url = GITLAB_HOST + '/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code'
    auth_url = url_for('.auth', _external=True)
    url = url.format(client_id=GITLAB_APPID, redirect_uri=auth_url)
    return redirect(url)


class GitlabToken(object):

    def __init__(self, code=None, token_json=None):
        logging.debug('instance gitlab token. code: %s, token_json:%s' % (code, token_json))

        if code:
            data = self._auth(code)
        else:
            data = token_json
        self.token_json = data

        self.access_token = data['access_token']
        self.expires_at = datetime.now() + timedelta(seconds=7000)
        self.refresh_token = data['refresh_token']

    def __str__(self):
        return "<access_token: %s, expires_at: %s>" % (self.access_token, self.expires_at)

    def _auth(self, code):
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
            abort(400)
        return r.json()

    def _refresh_token(self):
        url = GITLAB_HOST + '/oauth/token'
        params = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "scope": "api"
        }

        r = requests.post(url, params=params)
        logging.debug('result:', url, params, r.content, r.status_code)
        if r.status_code != 200:
            abort(400)
        return r.json()

    def is_valid(self):
        return self.access_token and self.expires_at and datetime.now() < self.expires_at

    def refresh(self):
        data = self._refresh_token()
        self.access_token = data['access_token']
        self.expires_at = datetime.now() + timedelta(seconds=7000)
        self.refresh_token = data['refresh_token']

    def get_token_or_refresh(self):
        if not self.is_valid():
            self.refresh_token()

        return self.access_token

    @classmethod
    def get_instance(cls):
        code = request.args.get('code')

        token_json = session.get('token_json')
        logging.debug('token: %s' % token_json)
        if token_json:
            token = GitlabToken(token_json=token_json)
        elif code:
            token = GitlabToken(code=code)
            session['token_json'] = token.token_json
        else:
            abort(401)

        return token


@app.route('/')
def hello_world():
    logging.debug('hello world')
    return 'Hello, World!'


@app.route('/auth')
def auth():
    token = GitlabToken.get_instance()

    return token.access_token


@app.route('/issues')
def issues():
    token = GitlabToken.get_instance()
    url = GITLAB_HOST + '/api/v3/issues?labels=calendar'
    r = requests.get(url, headers={
        "Authorization": "Bearer " + token.access_token
    })

    return jsonify(r.json())


@app.route('/milestones')
def api_milestones():
    token = GitlabToken.get_instance()
    url = GITLAB_HOST + '/api/v3/projects'
    r = requests.get(url, headers={
        "Authorization": "Bearer " + token.access_token
    })

    milestones = []
    for project in r.json():
        url = GITLAB_HOST + '/api/v3/projects/%s/milestones' % project['id']
        r = requests.get(url, headers={
            "Authorization": "Bearer " + token.access_token
        })
        logging.debug('milestones: %s' % r.content)
        if r.json():
            milestones += r.json()

    return jsonify(milestones)


@app.route('/api/calendar')
def api_calendar():
    events = []

    token = GitlabToken.get_instance()
    url = GITLAB_HOST + '/api/v3/issues?labels=calendar&per_page=100'
    r = requests.get(url, headers={
        "Authorization": "Bearer " + token.access_token
    })

    logging.debug('result issues: %s' % r.json())

    for issue in r.json():
        data = {
            "title": issue.get('title'),
            "start": issue.get('created_at')[:10],
            "backgroundColor": "#00a65a",
            "borderColor": "#00a65a"
        }

        if issue.get('due_date'):
            data["end"] = issue.get('due_date')

        events.append(data)

    return jsonify(events)
