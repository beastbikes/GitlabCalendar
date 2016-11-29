from gevent.wsgi import WSGIServer
from app import app

app.debug = True
http_server = WSGIServer(('0.0.0.0', 5000), app, log=app.logger)
http_server.serve_forever()
