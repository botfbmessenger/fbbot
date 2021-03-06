#!/usr/bin/env python

import requests
import urllib
import json
import os
import re
import pprint


from flask import Flask
from flask import request
from flask import make_response
from datetime import datetime as DateTime, timedelta as TimeDelta
from googleapiclient.discovery import build


# Flask app should start in global layout
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)

    print("Request:")
    print(json.dumps(req, indent=4))

    res = makeWebhookResult(req)

    res = json.dumps(res, indent=4)
    print(res)
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

def makeWebhookResult(req):
    if req is None:
        return {}
    
    result = req.get("result")
    action = result.get("action")
    parameters = result.get("parameters")
    
    if action == "browse.search.products":
        result = req.get("result")
        parameters = result.get("parameters")
        #color = parameters.get("color")
        #cat = parameters.get("catalog-category")
        if ((req.get("originalRequest") is not None) and (req.get("originalRequest").get("source") == "facebook")):
            
            key = "<CSE-KEY>"
            cseid = "<CX-ID>"
            keyword = parameters.get("search")
            results = google_search(keyword, key, cseid, num=10)
            
            for result in results:
                pprint.pprint(result)
            
            speech = "Here are the search results:"
            
            return {
                "speech": "",
                "messages": [
                    {
                        "type": 0,
                        "platform": "facebook",
                        "speech": speech
                    },
                    {
                        "type": 4,
                        "platform": "facebook",
                        "payload": {
                            "facebook": {
                                "attachment": {
                                    "type": "template",
                                    "payload": {
                                        "template_type": "generic",
                                        "elements": [
                                            {
                                                "title":"WelcometoPeter'\''sHats",
                                                "image_url":"https://petersfancybrownhats.com/company_image.png",
                                                "subtitle":"We'\''vegottherighthatforeveryone.",
                                                "default_action": {
                                                    "type":"web_url",
                                                    "url":"https://peterssendreceiveapp.ngrok.io/view?item=103",
                                                    "webview_height_ratio":"tall",
                                                    "fallback_url":"https://peterssendreceiveapp.ngrok.io/"
                                                },
                                                "buttons": [
                                                    {
                                                        "type":"web_url",
                                                        "url":"https://petersfancybrownhats.com",
                                                        "title":"ViewWebsite"
                                                    },
                                                    {
                                                        "type":"postback",
                                                        "title":"StartChatting",
                                                        "payload":"DEVELOPER_DEFINED_PAYLOAD"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        else:
            rq = requests.get("http://www.lanebryant.com/lanebryant/search?Ntt=" + color + " " + cat + "&format=JSON")
            jdata = json.loads(rq.text)
            speech = "I found " + str(jdata["contents"][0]["MainContent"][0]["MainContent"][0]["contents"][0]["totalNumRecs"]) + " " + color + " " + cat + " products." 
    elif req.get("result").get("action") == "promo_sign_up":
        result = req.get("result")
        parameters = result.get("parameters")
        #color = parameters.get("color")
        #cat = parameters.get("catalog-category")
        if ((req.get("originalRequest") is not None) and (req.get("originalRequest").get("source") == "facebook")):
            return {
                "data": {
                    "facebook": {
                        "text": "Pick a color:",
                        "quick_replies": [
                            {
                                "content_type": "text",
                                "title": "Red",
                                "payload": "red"
                            },
                            {
                                "content_type": "text",
                                "title": "Green",
                                "payload": "green"
                            }
                        ]
                    }
                }
            }
        else:
            speech = "I found products."
    elif action == "order_status_receipt":
        #result = req.get("result")
        #parameters = result.get("parameters")
        zipcode = parameters.get("zipcode")
        ordernum = parameters.get("order-number")
        ordernum = re.sub('\W+','', ordernum)
        ordernum = ordernum.upper()
        
        #Call ATG Order API
        rq = requests.post("https://www.lanebryant.com/lanebryant/homepage/includes/order-response-html.jsp", data={'orderNum': ordernum, 'billingZip': zipcode, 'Action': 'fetchODDetails'})
        
        #Get Order JSON from the response
        jdata = getOrderJSON(rq)
        
        #Order Status Details
        matchObj = rq.text[rq.text.find("order-status-label")+20:rq.text.find("<", rq.text.find("order-status-label"))]
        matchDate = rq.text[rq.text.find("mar-date")+10:rq.text.find("<", rq.text.find("mar-date"))]
        matchDate = matchDate.strip().replace('\n', '').replace(' ','')
        date = DateTime.now()
        
        if len(matchObj) < 50:
            print ("matchObj : ", matchObj)
            print ("matchDate : ", matchDate)
            status = matchObj
            date = DateTime.strptime(matchDate, '%m/%d/%Y') + TimeDelta(days=7)
        else:
            status = "No match!!"
        
        speech = getOrderStatusResponse(status, date)
        #END Order Status Details
        
        #Order Item Variables
        elements = ""
        count = len(jdata["data"]["cartItems"])
        for mc in jdata["data"]["cartItems"]:
            element = "{\"title\": " + "\"" + str(mc["name"]) + "\"," + "\"quantity\": " + str(mc["quantity"]) + "," + "\"price\": " + str(mc["totalPrice"]) + "," + "\"currency\":\"USD\"," + "\"image_url\": \"https:" + str(mc["imageURL"]) + "\"}"
            if(count != 1):
                element = element + ","
                count = count - 1
            elements = elements + element
        json_elements = json.loads("["+elements+"]")
        
        #Order Summary Variables
        subtotal = jdata["data"]["cartSummary"]["totalPreSvng"]
        shipping_cost = jdata["data"]["cartSummary"]["estmShipping"]
        if shipping_cost == 'FREE':
            shipping_cost = '0.0'
        total_tax = jdata["data"]["cartSummary"]["payment"]["taxesAndDuties"]
        total_cost = jdata["data"]["cartSummary"]["totalPostSvng"]
        
        #Order Adjustment Variables
        adj_elements = ""
        adj_zero = 0
        adj_count = len(jdata["data"]["cartSummary"]["savings"])
        if adj_count != 0:
            for adj in jdata["data"]["cartSummary"]["savings"]:
                if adj.get('value'):
                    adj_element = "{\"name\": " + "\"" + str(adj["message"]).replace("[","").replace("]","") + "\"," + "\"amount\": " + str(int(float(adj["value"]))) + "}"
                else:
                    adj_element = "{\"name\": " + "\"" + str(adj["message"]).replace("[","").replace("]","") + "\"," + "\"amount\": " + str(adj_zero) + "}"
                if(adj_count != 1):
                    adj_element = adj_element + ","
                    adj_count = adj_count - 1
                adj_elements = adj_elements + adj_element
            print (adj_elements)
            adj_json = json.loads("["+adj_elements+"]")
        else:
            adj_json = json.loads("[]")
        
        if ((req.get("originalRequest") is not None) and (req.get("originalRequest").get("source") == "facebook")):
            return {
                    "speech": "",
                    "messages": [{
                        "type": 0,
                        "platform": "facebook",
                        "speech": speech
                    },
                    {
                        "type": 4,
                        "platform": "facebook",
                        "payload": {
                            "facebook": {
                                "attachment": {
                                    "type": "template",
                                    "payload": {
                                        "template_type": "receipt",
                                        "recipient_name": "Ascena Retail",
                                        "order_number": ordernum,
                                        "currency": "USD",
                                        "payment_method": "Visa 2345",
                                        "timestamp": "1519420539",
                                        "address": {
                                            "street_1": "200 Heritage Drive",
                                            "street_2": "",
                                            "city": "Pataskala",
                                            "postal_code": "43062",
                                            "state": "OH",
                                            "country": "US"
                                        },
                                        "summary": {
                                            "subtotal": subtotal,
                                            "shipping_cost": shipping_cost,
                                            "total_tax": total_tax,
                                            "total_cost": total_cost
                                        },
                                        "adjustments": adj_json,
                                        "elements": json_elements
                                    }
                                }
                            }
                        }
                    }]
                }
        else:
            rq = requests.get("http://www.lanebryant.com/lanebryant/search?Ntt=" + color + " " + cat + "&format=JSON")
            jdata = json.loads(rq.text)
            speech = "I found " + str(jdata["contents"][0]["MainContent"][0]["MainContent"][0]["contents"][0]["totalNumRecs"]) + " " + color + " " + cat + " products."         
    elif req.get("result").get("action") == "promos":
        result = req.get("result")
        headers = {'HOST': 'sit.catherines.com'}
        rq = requests.get("https://23.34.4.174/static/promo_01?format=json", headers=headers, verify=False)
        jdata = json.loads(rq.text)
        
        if ((req.get("originalRequest") is not None) and (req.get("originalRequest").get("source") == "facebook")):
            temp = "\"image_url\": \"https://call-center-agent.herokuapp.com/static/lb-logo.png\",\"default_action\":{\"type\": \"web_url\",\"url\": \"http://www.lanebryant.com/\"}}"
            elements = ""
            count = len(jdata["MainContent"])
            
            for mc in jdata["MainContent"]:
                element = "{\"title\": " + "\"" + str(mc["freeFormContent"]) + "\"," + temp
                if(count != 1):
                    element = element + ","
                    count = count - 1
                elements = elements + element
            
            json_elements = json.loads("["+elements+"]")
            return{
                "data": {
                    "facebook": {
                        "attachment": {
                            "type": "template",
                            "payload": {
                                "template_type": "list",
                                "elements": json_elements
                            }
                        }
                    }
                }
            }
        else:    
            speech = "Promos are "
            for mc in jdata["MainContent"]:
                speech = speech + str(mc["freeFormContent"]) + "... "
    elif ((req.get("result").get("action") == "Order_Status_yes") or (req.get("result").get("action") == "checkout.order.status")):
        result = req.get("result")
        parameters = result.get("parameters")
        zipcode = parameters.get("zipcode")
        ordernum = parameters.get("order-number")
        ordernum = re.sub('\W+','', ordernum)
        ordernum = ordernum.upper()
        
        rq = requests.post("https://www.lanebryant.com/lanebryant/homepage/includes/order-response-html.jsp", data={'orderNum': ordernum, 'billingZip': zipcode, 'Action': 'fetchODDetails'})
        #print rq.text
        cartJSON = rq.text[rq.text.find("cart-json")+35:rq.text.find("</script>", rq.text.find("cart-json"))]
        order_json = json.loads(cartJSON)
        
        matchObj = rq.text[rq.text.find("order-status-label")+20:rq.text.find("<", rq.text.find("order-status-label"))]
        matchDate = rq.text[rq.text.find("mar-date")+10:rq.text.find("<", rq.text.find("mar-date"))]
        matchDate = matchDate.strip().replace('\n', '').replace(' ','')
        
        date = DateTime.now()
        present = DateTime.now()
        
        if len(matchObj) < 50:
            print ("matchObj : ", matchObj)
            print ("matchDate : ", matchDate)
            status = matchObj
            date = DateTime.strptime(matchDate, '%m/%d/%Y') + TimeDelta(days=5)
            orderFound = "I found your order. Here is the order status."
        else:
            status = "Please check the order number or zipcode and try again."
            orderFound = "Sorry! I could not find that order."
            print ("No match!!")
            
        if date >= present:
            if status == 'Shipped':
                speech = "The status of your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Partially Shipped':
                speech = "The status of your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Canceled':
                speech = "The status of your order is " + status + ". Please reach out to the customer support for more details about the order."
            elif status == 'Processing':
                speech = "The status of your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
            else:
                speech = status
        else:
            if status == 'Shipped':
                speech = "The status of your order is " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Partially Shipped':
                speech = "The status of your order is " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Canceled':
                speech = "The status of your order is " + status + ". Please reach out to the customer support for more details about the order."
            elif status == 'Processing':
                speech = "The status of your order is " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
            else:
                speech = status
        
        if ((req.get("originalRequest") is not None) and (req.get("originalRequest").get("source") == "facebook")):
            return {
                    "speech": "",
                    "messages": [{
                        "type": 0,
                        "platform": "facebook",
                        "speech": orderFound
                    },
                    {
                        "type": 0,
                        "platform": "facebook",
                        "speech": speech
                    }]
                } 
        
    elif req.get("result").get("action") == "Order_Status_no":
        result = req.get("result")
        parameters = result.get("parameters")
        zipcode = parameters.get("zipcode")
        email = parameters.get("email")
        ordertime = parameters.get("order-time")
        
        #TODO - Need to put here the API to get order number using email, zipcode and the timeframe
        if zipcode == '20166':
            ordernum = 'OJTW022967052'
        elif zipcode == '37122':
            ordernum = 'OJTW027567667'
        elif zipcode == '19148':
            ordernum = 'OJTW027678055'
        elif zipcode == '27217':
            ordernum = 'OLBW009566347'
        elif zipcode == '43081':
            ordernum = 'OLBW025892656'
        else:
            ordernum = 'OLBW025892656'
            zipcode = '43081'
            
        rq = requests.post("https://www.lanebryant.com/lanebryant/homepage/includes/order-response-html.jsp", data={'orderNum': ordernum, 'billingZip': zipcode, 'Action': 'fetchODDetails'})
        cartJSON = rq.text[rq.text.find("cart-json")+35:rq.text.find("</script>", rq.text.find("cart-json"))]
        jdata = json.loads(cartJSON)
        
        #Order Status Details
        matchObj = rq.text[rq.text.find("order-status-label")+20:rq.text.find("<", rq.text.find("order-status-label"))]
        matchDate = rq.text[rq.text.find("mar-date")+10:rq.text.find("<", rq.text.find("mar-date"))]
        matchDate = matchDate.strip().replace('\n', '').replace(' ','')
        date = DateTime.now()
        present = DateTime.now()
        
        if len(matchObj) < 50:
            print ("matchObj : ", matchObj)
            print ("matchDate : ", matchDate)
            status = matchObj
            date = DateTime.strptime(matchDate, '%m/%d/%Y') + TimeDelta(days=5)
            orderFound = "I found your order. Here is the order status."
        else:
            status = "Please check the email, order time or zipcode and try again."
            orderFound = "Sorry! I could not find your order."
            print ("No match!!")
            
        if date >= present:
            if status == 'Shipped':
                speech = "The status of your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Partially Shipped':
                speech = "The status of your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Canceled':
                speech = "The status of your order is " + status + ". Please reach out to the customer support for more details about the order."
            elif status == 'Processing':
                speech = "The status of your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
            else:
                speech = status
        else:
            if status == 'Shipped':
                speech = "The status of your order is " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Partially Shipped':
                speech = "The status of your order is " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
            elif status == 'Canceled':
                speech = "The status of your order is " + status + ". Please reach out to the customer support for more details about the order."
            elif status == 'Processing':
                speech = "The status of your order is " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
            else:
                speech = status
        #END Order Status Details
        
        #Order Item Variables
        elements = ""
        count = len(jdata["data"]["cartItems"])
        for mc in jdata["data"]["cartItems"]:
            element = "{\"title\": " + "\"" + str(mc["name"]) + "\"," + "\"quantity\": " + str(mc["quantity"]) + "," + "\"price\": " + str(mc["totalPrice"]) + "," + "\"currency\":\"USD\"," + "\"image_url\": \"https:" + str(mc["imageURL"]) + "\"}"
            if(count != 1):
                element = element + ","
                count = count - 1
            elements = elements + element
        json_elements = json.loads("["+elements+"]")
        
        #Order Summary Variables
        subtotal = jdata["data"]["cartSummary"]["totalPreSvng"]
        shipping_cost = jdata["data"]["cartSummary"]["estmShipping"]
        if shipping_cost == 'FREE':
            shipping_cost = '0.0'
        total_tax = jdata["data"]["cartSummary"]["payment"]["taxesAndDuties"]
        total_cost = jdata["data"]["cartSummary"]["totalPostSvng"]
        
        #Order Adjustment Variables
        adj_elements = ""
        adj_zero = 0
        adj_count = len(jdata["data"]["cartSummary"]["savings"])
        if adj_count != 0:
            for adj in jdata["data"]["cartSummary"]["savings"]:
                if adj.get('value'):
                    adj_element = "{\"name\": " + "\"" + str(adj["message"]).replace("[","").replace("]","") + "\"," + "\"amount\": " + str(int(float(adj["value"]))) + "}"
                else:
                    adj_element = "{\"name\": " + "\"" + str(adj["message"]).replace("[","").replace("]","") + "\"," + "\"amount\": " + str(adj_zero) + "}"
                if(adj_count != 1):
                    adj_element = adj_element + ","
                    adj_count = adj_count - 1
                adj_elements = adj_elements + adj_element
            print (adj_elements)
            adj_json = json.loads("["+adj_elements+"]")
        else:
            adj_json = json.loads("[]")
        
        if ((req.get("originalRequest") is not None) and (req.get("originalRequest").get("source") == "facebook")):
            return {
                    "speech": "",
                    "messages": [{
                        "type": 0,
                        "platform": "facebook",
                        "speech": orderFound
                    },
                    {
                        "type": 0,
                        "platform": "facebook",
                        "speech": speech
                    },
                    {
                        "type": 0,
                        "platform": "facebook",
                        "speech": "Order details are as follows:"
                    },
                    {
                        "type": 4,
                        "platform": "facebook",
                        "payload": {
                            "facebook": {
                                "attachment": {
                                    "type": "template",
                                    "payload": {
                                        "template_type": "receipt",
                                        "recipient_name": "Ascena Retail",
                                        "merchant_name": ordernum,
                                        "order_number": ordernum,
                                        "currency": "USD",
                                        "payment_method": "Visa 2345",
                                        "timestamp": "1519420539",
                                        "summary": {
                                            "subtotal": subtotal,
                                            "shipping_cost": shipping_cost,
                                            "total_tax": total_tax,
                                            "total_cost": total_cost
                                        },
                                        "adjustments": adj_json,
                                        "elements": json_elements
                                    }
                                }
                            }
                        }
                    }]
                }
        else:
            rq = requests.get("http://www.lanebryant.com/lanebryant/search?Ntt=" + color + " " + cat + "&format=JSON")
            jdata = json.loads(rq.text)
            speech = "I found " + str(jdata["contents"][0]["MainContent"][0]["MainContent"][0]["contents"][0]["totalNumRecs"]) + " " + color + " " + cat + " products."         
    else:
        return{}
    print("Response:")
    print(speech)
    return {
        "speech": speech,
        "displayText": speech,
        #"data": {},
        # "contextOut": [],
        "source": "apiai-onlinestore-search"
    }


def getOrderJSON(rq):
    cartJSON = rq.text[rq.text.find("cart-json")+35:rq.text.find("</script>", rq.text.find("cart-json"))]
    return json.loads(cartJSON)

def getOrderStatusResponse(status, date):
    present = DateTime.now()
    if date >= present:
        if status == 'Shipped':
            speech = "Your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
        elif status == 'Partially Shipped':
            speech = "Your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
        elif status == 'Canceled':
            speech = "Your order is " + status + ". Please reach out to the customer support for more details about the order."
        elif status == 'Processing':
            speech = "Your order is " + status + ". You should receive the package by " + date.strftime('%m/%d/%Y') + "."
        else:
            speech = "Sorry! I could not find that order. Please check the order number or zipcode and try again."
    else:
        if status == 'Shipped':
            speech = "Your order has been " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
        elif status == 'Partially Shipped':
            speech = "Your order has been " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
        elif status == 'Canceled':
            speech = "Your order has been " + status + ". Please reach out to the customer support for more details about the order."
        elif status == 'Processing':
            speech = "Your order has been " + status + ". You should have received the package by " + date.strftime('%m/%d/%Y') + "."
        else:
            speech = "Sorry! I could not find that order. Please check the order number or zipcode and try again."    
    return speech

def google_search(search_term, key, cseid, **kwargs):
    service = build("customsearch", "v1", developerKey=key)
    res = service.cse().list(q=search_term, cx=cseid, **kwargs).execute()
    print("Search Result: ", res)
    return res['items']

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    print ("Starting app on port %d" % port)

    app.run(debug=True, port=port, host='0.0.0.0')
