import eventlet

# "import encodings.idna" is a fix for "unknown encoding: idna" error
# which we saw occurring's on a user's computer and crashing the app
# in result
import encodings.idna
import logging
import argparse

import time
import json
import traceback
import sys
import subprocess
import psutil
import functools as fn

from flask import Flask, Response, request
from flask_socketio import emit, SocketIO

from bloomberg.utils import openBloombergSession, startBbcommIfNecessary, BrokenSessionException
from requests import latest, historical, intraday, subscribe, unsubscribe, dev
from requests.utils import allowCORS
from subscriptions import handleSubscriptions
from utils import get_main_dir, main_is_frozen

VERSION = "2.6"
app = Flask(__name__)

app.url_map.strict_slashes = False

app.allSubscriptions = {}
app.bloombergHits = {}
app.sessionForRequests = None
app.sessionForSubscriptions = None

app.register_blueprint(latest.blueprint, url_prefix='/latest')
app.register_blueprint(historical.blueprint, url_prefix='/historical')
app.register_blueprint(intraday.blueprint, url_prefix='/intraday')
app.register_blueprint(subscribe.blueprint, url_prefix='/subscribe')
app.register_blueprint(unsubscribe.blueprint, url_prefix='/unsubscribe')
socketio = SocketIO(app, async_mode="eventlet")

@app.route('/status', methods = ['OPTIONS'])
@app.route('/subscriptions', methods = ['OPTIONS'])
@app.route('/latest', methods = ['OPTIONS'])
@app.route('/historical', methods = ['OPTIONS'])
@app.route('/intraday', methods = ['OPTIONS'])
@app.route('/subscribe', methods = ['OPTIONS'])
@app.route('/unsubscribe', methods = ['OPTIONS'])
def tellThemWhenCORSIsAllowed():
    response = Response("")
    response.headers['Access-Control-Allow-Origin'] = allowCORS(request.headers.get('Origin'))
    response.headers['Access-Control-Allow-Methods'] = ", ".join(["GET", "OPTIONS"])
    return response

@app.route('/status', methods = ['GET'])
def status():
    status = "UP" if app.sessionForRequests or app.sessionForSubscriptions else "DOWN"
    response = Response(
        json.dumps({
            "status": status,
            "version": VERSION,
            "metrics": {
                "subscriptions": fn.reduce(lambda xs, x: xs + len(x[1]), app.allSubscriptions.items(), 0),
                "bloombergHits": app.bloombergHits
            }
        }).encode(),
        status=200,
        mimetype='application/json')
    response.headers['Access-Control-Allow-Origin'] = allowCORS(request.headers.get('Origin'))
    return response

@app.route('/subscriptions', methods = ['GET'])
def subscriptions():
    response = Response(
        json.dumps(app.allSubscriptions).encode(),
        status=200,
        mimetype='application/json')
    response.headers['Access-Control-Allow-Origin'] = allowCORS(request.headers.get('Origin'))
    return response

def wireUpBlpapiImplementation(blpapi):
    import bloomberg.utils
    bloomberg.utils.__dict__["blpapi"] = blpapi
    subscribe.__dict__["blpapi"] = blpapi
    import subscriptions
    subscriptions.__dict__["blpapi"] = blpapi
    unsubscribe.__dict__["blpapi"] = blpapi
    dev.__dict__["blpapi"] = blpapi

def wireUpDevelopmentDependencies():
    global blpapi
    blpapi = eventlet.import_patched("blpapi_simulator")
    app.register_blueprint(dev.blueprint, url_prefix='/dev')

def wireUpProductionDependencies():
    global blpapi
    import blpapi

    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    startBbcommIfNecessary()

def main(port = 6659):
    wireUpBlpapiImplementation(blpapi)

    server = None
    try:
        try:
            app.sessionForRequests = openBloombergSession()
            app.sessionForSubscriptions = openBloombergSession()
            app.allSubscriptions = {}
        except:
            traceback.print_exc()
        socketio.start_background_task(lambda: handleSubscriptions(app, socketio))
        socketio.run(app, port = port)
    except KeyboardInterrupt:
        print("Ctrl+C received, exiting...")
    finally:
        if app.sessionForRequests is not None:
            app.sessionForRequests.stop()
        if app.sessionForSubscriptions is not None:
            app.sessionForSubscriptions.stop()
        if server is not None:
            server.socket.close()

if main_is_frozen():
    wireUpProductionDependencies()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--simulator', action='store_true',
                        help='simulate Bloomberg API (instead of using real connection)')
    parser.add_argument('--log', choices=['critical', 'error', 'warn', 'info', 'debug'],
                        help='log level')
    parser.add_argument('--port', type=int, default=6659,
                        help='port number (default: 6659)')

    args = parser.parse_args()

    if args.log is not None:
        logging.basicConfig(level=getattr(logging, args.log.upper(), None))

    if args.simulator:
        print("Using blpapi_simulator")
        wireUpDevelopmentDependencies()
    else:
        wireUpProductionDependencies()
    main(args.port)

