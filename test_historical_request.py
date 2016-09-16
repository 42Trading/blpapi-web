from server import extractHistoricalSecurityPricing, extractErrors
from blpapi_mock import *
import pytest

def test_simple():
    message = Message({
        "securityData": List([Map({
            "security": "L Z7 Comdty",
            "fieldData": List([
                Map({
                    "date": "2006-01-31",
                    "PX_LAST": 90
                }),
                Map({
                    "date": "2006-02-01",
                    "PX_LAST": 90.05
                })
            ])
        })])
    })
    response = extractHistoricalSecurityPricing(message)
    assert len(response) == 2
    assert response[0]["date"] == "2006-01-31"
    assert response[1]["date"] == "2006-02-01"

def test_extract_multiple_fields():
    message = Message({
        "securityData": List([Map({
            "security": "L Z7 Comdty",
            "fieldData": List([
                Map({
                    "date": "2006-01-31",
                    "PX_LAST": 90,
                    "ASK": 90
                })
            ])
        })])
    })
    response = extractHistoricalSecurityPricing(message)
    print(response)
    assert len(response) == 1
    assert len(response[0]["values"][0]["fields"]) == 2

def test_response_error():
    message = Message({
        "responseError": Map({
            "category": "CATEGORY",
            "subcategory": "SUBCATEGORY",
            "message": "MESSAGE"
        })
    })
    response = extractHistoricalSecurityPricing(message)
    errors = extractErrors(message)
    assert len(response) == 0
    assert len(errors) == 1
    assert errors[0] == "CATEGORY/SUBCATEGORY MESSAGE"