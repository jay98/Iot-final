# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_flex_quickstart]
import logging

from flask import Flask, request, render_template
import pyrebase
import ibmiotf.application
import json
from time import sleep, time
import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.svm import SVC
import datetime
import os


config = {
    "apiKey": "",
    "authDomain": "",
    "databaseURL": "",
    "projectId": "",
    "storageBucket": "",
    "messagingSenderId": ""
}

firebase = pyrebase.initialize_app(config)

db = firebase.database()


app = Flask(__name__, static_folder='templates')
svclassifier = load('door_model.joblib')

logging.info("Loaded models")
print("Loaded models")


def myCallback(cmd):
    if cmd.event == "room_enter":
        payload = json.loads(cmd.payload)
        currentDT = datetime.datetime.now()
        db.child("Entries").child(payload["entered"]).push(str(currentDT))
    if cmd.event == "doorData":
        payload = json.loads(cmd.payload)
        # print(cmd.payload)
        df = pd.read_json(payload, orient='records')
        estimate(svclassifier.predict(df))


def estimate(l):
    op = 0
    close = 0
    for num in l:
        if num == 1:
            op += 1
        else:
            close += 1

    if op > close:
        print("open")
        logging.info('Open')
        myData = {'doorStatus': 'Open'}
        client.publishEvent(
            "door_sensor", "b827eb0acdd1", "doorStatus", "json", myData)
    else:
        print("close")
        logging.info('Close')
        myData = {'doorStatus': 'Close'}
        client.publishEvent(
            "door_sensor", "b827eb0acdd1", "doorStatus", "json", myData)


@app.route('/', methods=['GET'])
def hello():
    print("Print GET")
    logging.info('LOG GET')
    entries = db.child("Entries").get().val()
    return render_template("index.html", vals=entries)


@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    options = ibmiotf.application.ParseConfigFile("server.cfg")
    client = ibmiotf.application.Client(options)
    print("Connecting")
    client.connect()
    sleep(2)
    client.deviceEventCallback = myCallback
    client.subscribeToDeviceEvents(event="room_enter")
    client.subscribeToDeviceEvents(event="doorData")
    app.run(host='127.0.0.1', port=8080)
# [END gae_flex_quickstart]
