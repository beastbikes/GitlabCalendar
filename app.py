import os
import logging
from datetime import datetime, timedelta

import requests
from flask import Flask, request, session, url_for, redirect, abort, jsonify, render_template


app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']


logging.basicConfig(level='DEBUG')

GITLAB_HOST = os.environ['GITLAB_HOST']
GITLAB_APPID = os.environ['GITLAB_APPID']
GITLAB_APP_SECRET = os.environ['GITLAB_APP_SECRET']

# time tags value is hour for this tag
DATE_TAGS = {
    '0.25D': 2,
    '0.5D': 5,
    '1D': 24,
    '2D': 48,
}

DATE_FORMAT = '%Y-%m-%d'


@app.errorhandler(401)
def not_login_handler(error):
    url = GITLAB_HOST + '/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code'
    auth_url = url_for('.index', _external=True)
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
            "redirect_uri": url_for('.index', _external=True)
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
def index():
    token = GitlabToken.get_instance()
    url = GITLAB_HOST + '/api/v3/groups'
    r = requests.get(url, headers={
        "Authorization": "Bearer " + token.access_token
    })
    data = reversed(r.json())
    logging.debug('groups: %s' % r.content.decode())
    current_group_id = r.json()[0]['id'] if 'current_group_id' not in session else session['current_group_id']

    return render_template('index.html', groups=data, current_group_id=int(current_group_id))


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
    current_group_id = request.args.get('current_group_id')
    session['current_group_id'] = current_group_id
    events = []

    token = GitlabToken.get_instance()
    url = GITLAB_HOST + '/api/v3/groups/%s/issues?per_page=100&state=all' % current_group_id
    logging.debug('url: %s' % url)
    r = requests.get(url, headers={
        "Authorization": "Bearer " + token.access_token
    })

    logging.debug('result issues: %s' % r.content.decode())

    for issue in r.json():
        data = {
            "title": issue.get('title'),
            "start": issue.get('created_at')[:10],
            "allDay": True,
        }

        if issue.get('state') == 'closed':
            data['backgroundColor'] = '#00a65a'
            data['borderColor'] = '#00a65a'

        due_date = issue.get('due_date')
        if due_date:
            due_date_time = datetime.strptime(due_date, DATE_FORMAT)
            data["end"] = due_date
            labels = issue.get('labels')
            if labels:
                for label in labels:
                    date_tag = DATE_TAGS.get(label)
                    fixed_start = due_date_time - timedelta(hours=date_tag)
                    if fixed_start.hour == 0:
                        fixed_start = fixed_start.strftime(DATE_FORMAT)
                    else:
                        data['allDay'] = False

                    if date_tag:
                        data['start'] = fixed_start
                        data['title'] += label
                        break
                else:
                    data['backgroundColor'] = '#ad8d43'
                    data['borderColor'] = '#ad8d43'
            else:
                data['backgroundColor'] = '#ad8d43'
                data['borderColor'] = '#ad8d43'

            if issue.get('state') != 'closed':
                if datetime.now() > due_date_time:
                    data['backgroundColor'] = '#f56954'
                    data['borderColor'] = '#f56954'

        events.append(data)

    return jsonify(events)
