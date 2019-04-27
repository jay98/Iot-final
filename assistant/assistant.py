import os
import logging
import json

import ibmiotf.application
from time import sleep, time
# import numpy as np
# import pandas as pd


from imutils.video import VideoStream
import face_recognition
import imutils
import pickle
import cv2

from click import get_app_dir
import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials

from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc
)
import assistant_helpers
# import browser_helpers

ASSISTANT_API_ENDPOINT = 'embeddedassistant.googleapis.com'
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5
PLAYING = embedded_assistant_pb2.ScreenOutConfig.PLAYING
DETECTED = 0
PERSON = ""
OWNER = "Randy"
ASSISTANT = 0


class SampleTextAssistant(object):
    """Sample Assistant that supports text based conversations.

    Args:
      language_code: language for the conversation.
      device_model_id: identifier of the device model.
      device_id: identifier of the registered device instance.
      display: enable visual display of assistant response.
      channel: authorized gRPC channel for connection to the
        Google Assistant API.
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
    """

    def __init__(self, language_code, device_model_id, device_id,
                 display, channel, deadline_sec):
        self.language_code = language_code
        self.device_model_id = device_model_id
        self.device_id = device_id
        self.conversation_state = None
        # Force reset of first conversation.
        self.is_new_conversation = True
        self.display = display
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(
            channel
        )
        self.deadline = deadline_sec

    def __enter__(self):
        return self

    def __exit__(self, etype, e, traceback):
        if e:
            return False

    def assist(self, text_query):
        """Send a text request to the Assistant and playback the response.
        """
        def iter_assist_requests():
            config = embedded_assistant_pb2.AssistConfig(
                audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                    encoding='LINEAR16',
                    sample_rate_hertz=16000,
                    volume_percentage=0,
                ),
                dialog_state_in=embedded_assistant_pb2.DialogStateIn(
                    language_code=self.language_code,
                    conversation_state=self.conversation_state,
                    is_new_conversation=self.is_new_conversation,
                ),
                device_config=embedded_assistant_pb2.DeviceConfig(
                    device_id=self.device_id,
                    device_model_id=self.device_model_id,
                ),
                text_query=text_query,
            )
            # Continue current conversation with later requests.
            self.is_new_conversation = False
            if self.display:
                config.screen_out_config.screen_mode = PLAYING
            req = embedded_assistant_pb2.AssistRequest(config=config)
            assistant_helpers.log_assist_request_without_audio(req)
            yield req

        text_response = None
        html_response = None
        for resp in self.assistant.Assist(iter_assist_requests(),
                                          self.deadline):
            assistant_helpers.log_assist_response_without_audio(resp)
            if resp.screen_out.data:
                html_response = resp.screen_out.data
            if resp.dialog_state_out.conversation_state:
                conversation_state = resp.dialog_state_out.conversation_state
                self.conversation_state = conversation_state
            if resp.dialog_state_out.supplemental_display_text:
                text_response = resp.dialog_state_out.supplemental_display_text
        return text_response, html_response


def myCallback(cmd):
    global DETECTED
    global PERSON

    if cmd.event == "room_enter":
        payload = json.loads(cmd.payload)
        print(payload["entered"])
        DETECTED = time()
        PERSON = payload["entered"]
    elif cmd.event == "doorStatus":
        payload = json.loads(cmd.payload)
        sleep(2)
        if payload["doorStatus"] == "Open":
            if time() - DETECTED < 20:
                print(PERSON)
                if PERSON == OWNER:
                    # ASSISTANT.assist(text_query="set the bed light to green")
                    # sleep(1)

                    ASSISTANT.assist(
                        text_query="broadcast welcome home " + OWNER)
                    sleep(2)
                    ASSISTANT.assist(text_query="turn on the lamp")
                    # sleep(3)
                    # ASSISTANT.assist(text_query="set the bed light to cyan")
                else:
                    # ASSISTANT.assist(
                    #     text_query="set the bed light to red")
                    # sleep(1)
                    ASSISTANT.assist(
                        text_query="broadcast this is not your room" + PERSON + " get out!")
            else:
                print("Person empty")
                PERSON = ""


def main(api_endpoint, credentials,
         device_model_id, device_id, lang, display, verbose,
         grpc_deadline, *args, **kwargs):

    FRAME_THRESHOLD = 2
    LAST_TURNON_THRESHOLD = 30
    LAST_SEND = 0

    global ASSISTANT

    cascade = "./haarcascade_frontalface_default.xml"
    model = "./jay_randy.pickle"

    options = ibmiotf.application.ParseConfigFile("rasp.cfg")

    client = ibmiotf.application.Client(options)
    client.connect()
    client.deviceEventCallback = myCallback
    client.subscribeToDeviceEvents(event="room_enter")
    client.subscribeToDeviceEvents(event="doorStatus")


# load the known faces and embeddings along with OpenCV's Haar
# cascade for face detection
    print("[INFO] loading model + face detector...")
    data = pickle.loads(open(model, "rb").read())
    detector = cv2.CascadeClassifier(cascade)

# initialize the video stream and allow the camera sensor to warm up
    print("[INFO] starting video stream...")
    # vs = VideoStream(src=0).start()
    vs = VideoStream(usePiCamera=True).start()
    sleep(2.0)

  # Setup logging.
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

   # Load OAuth 2.0 credentials.
    try:
        with open(credentials, 'r') as f:
            credentials = google.oauth2.credentials.Credentials(token=None,
                                                                **json.load(f))
            http_request = google.auth.transport.requests.Request()
            credentials.refresh(http_request)
    except Exception as e:
        logging.error('Error loading credentials: %s', e)
        logging.error('Run google-oauthlib-tool to initialize '
                      'new OAuth 2.0 credentials.')
        return

    # Create an authorized gRPC channel.
    grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
        credentials, http_request, api_endpoint)
    logging.info('Connecting to %s', api_endpoint)

    with SampleTextAssistant(lang, device_model_id, device_id, display,
                             grpc_channel, grpc_deadline) as assistant:
        ASSISTANT = assistant

    owner_in_frames = 0

    while True:
        frame = vs.read()
        frame = imutils.resize(frame, width=500)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        rects = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(
            30, 30), flags=cv2.CASCADE_SCALE_IMAGE)

        boxes = [(y, x + w, y + h, x) for (x, y, w, h) in rects]

        encodings = face_recognition.face_encodings(rgb, boxes)

        names = []

        for encoding in encodings:

            matches = face_recognition.compare_faces(
                data["encodings"], encoding)
            name = "Unknown"

            if True in matches:

                matchedIdxs = [i for (i, b) in enumerate(matches) if b]
                counts = {}

                for i in matchedIdxs:
                    name = data["names"][i]
                    counts[name] = counts.get(name, 0) + 1
                name = max(counts, key=counts.get)
            names.append(name)

        # print(names)

        if OWNER in names:
            owner_in_frames += 1
            if owner_in_frames > FRAME_THRESHOLD:
                if(time() - LAST_SEND > LAST_TURNON_THRESHOLD):
                    LAST_SEND = time()
                    toSend = {'entered': OWNER}
                    client.publishEvent(
                        "test_laptop", "3052cb831a51", "room_enter", "json", toSend)
        else:
            if len(names) > 0:
                if(time() - LAST_SEND > LAST_TURNON_THRESHOLD):
                    LAST_SEND = time()
                    toSend = {'entered': names[0]}
                    client.publishEvent(
                        "test_laptop", "3052cb831a51", "room_enter", "json", toSend)
                    sleep(0.4)
            owner_in_frames = 0


if __name__ == '__main__':
    main(ASSISTANT_API_ENDPOINT, os.path.join(get_app_dir('google-oauthlib-tool'),
                                              'credentials.json'),
         'iot-final-f81f6-test-laptop-o4uo4h', 'Test-laptop', 'en-US', False, False,
         DEFAULT_GRPC_DEADLINE)
