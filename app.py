from flask import Flask, request
app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/auth')
def auth():
    print('data', request.data)
    return "ok"
