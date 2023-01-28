from flask import Flask, request
import os
import json
from google.oauth2 import service_account
from google.cloud import vision, storage
from google.cloud.storage.blob import Blob
import cv2

app = Flask(__name__)

gcp_key_json = os.environ["gcp_key"]
credentials = service_account.Credentials.from_service_account_info(
    json.loads(gcp_key_json)
)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)
storage_client = storage.Client(credentials=credentials)


@app.route("/")
def index():
    return "im a sussy poster"


@app.route("/analyze")
def analyze():
    imguri = request.args.get("imgUri")
    output = {"objects": [], "colors": [], "properties": []}

    blob = Blob.from_string(imguri, client=storage_client)
    image_data = blob.download_as_bytes()

    cvimage = cv2.imgdecode(image_data)
    cv2.imshow(cvimage)
    cv2.waitKey(1)

    image = vision.Image()
    image.source.image_uri = imguri

    objects = vision_client.object_localization(
        image=image
    ).localized_object_annotations
    # objects = client.object_localization(
    #   image=image).

    print("Number of objects found: {}".format(len(objects)))
    for object_ in objects:
        print("\n{} (confidence: {})".format(object_.name, object_.score))
        if object_.score >= 0.5:
            if object_.name not in output["objects"]:
                output["objects"].append(object_.name)

    return json.dumps(output)


app.run(host="0.0.0.0", port=80)
