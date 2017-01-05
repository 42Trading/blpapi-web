import json
from flask import Blueprint, current_app as app, request, Response

from bloomberg.utils import openBloombergSession, openBloombergService, sendAndWait
from bloomberg.extract import extractReferenceSecurityPricing, extractErrors
from utils import handleBrokenSession

from .utils import allowCORS, respond400, respond500

blueprint = Blueprint('latest', __name__)

def requestLatest(session, securities, fields):
    try:
        refDataService, _ = openBloombergService(session, "//blp/refdata")
        request = refDataService.createRequest("ReferenceDataRequest")

        request.set("returnFormattedValue", True)
        for security in securities:
            request.append("securities", security)

        for field in fields:
            request.append("fields", field)

        responses = sendAndWait(session, request)

        securityPricing = []
        for response in responses:
            securityPricing.extend(extractReferenceSecurityPricing(response))

        errors = []
        for response in responses:
            errors.extend(extractErrors(response))
        return { "response": securityPricing, "errors": errors }
    except Exception as e:
        raise

# ?field=...&field=...&security=...&security=...
@blueprint.route('/', methods = ['GET'])
def index():
    try:
        if app.sessionForRequests is None:
            app.sessionForRequests = openBloombergSession()
        if app.sessionForSubscriptions is None:
            app.sessionForSubscriptions = openBloombergSession()
            app.allSubscriptions = {}
    except Exception as e:
        handleBrokenSession(e)
        if app.client is not None:
            app.client.captureException()
        return respond500(e)
    try:
        securities = request.args.getlist('security') or []
        fields = request.args.getlist('field') or []
    except Exception as e:
        if app.client is not None:
            app.client.captureException()
        return respond400(e)

    try:
        payload = json.dumps(requestLatest(app.sessionForRequests, securities, fields)).encode()
    except Exception as e:
        handleBrokenSession(e)
        if app.client is not None:
            app.client.captureException()
        return respond500(e)

    response = Response(
        payload,
        status=200,
        mimetype='application/json')
    response.headers['Access-Control-Allow-Origin'] = allowCORS(request.headers.get('Origin'))
    return response


