from flask import Flask, request
import os
import json
from google.oauth2 import service_account
from google.cloud import vision, storage
import base64
import colorsys
import math
import requests

app = Flask(__name__)

gcp_key_json = os.environ["gcp_key"]
credentials = service_account.Credentials.from_service_account_info(
  json.loads(gcp_key_json))
vision_client = vision.ImageAnnotatorClient(credentials=credentials)
storage_client = storage.Client(credentials=credentials)

with open("colors.json") as f:
  colors = json.load(f)

@app.route("/")
def index():
  return "Howdy!"


@app.route("/analyze", methods=["POST"])
def analyze():
  # response.headers.add('Access-Control-Allow-Origin', '*')
  # imguri = request.args.get("imgUri")
  request_json = json.loads(request.data)

  imgdata = base64.b64decode(request_json["image"])
  room_type = request_json["room_type"]

  output = {
    "objects": [],
    "colors": [],
    "scoring": {
      "required_objects": {
        "score": 0,
      },
      "color": {
        "score": 0
      },
      "lighting": {
        "score": 0
      }
    },
    "recommendations": []
  }

  # Get google api image
  image = vision.Image(content=imgdata)

  # Request object detection
  objects = vision_client.object_localization(
    image=image).localized_object_annotations

  print("Number of objects found: {}".format(len(objects)))
  for object_ in objects:
    print("\n{} (confidence: {})".format(object_.name, object_.score))
    if object_.score >= 0.1:
      if object_.name not in output["objects"]:
        output["objects"].append(object_.name)

  response = vision_client.label_detection(image=image)
  labels = response.label_annotations

  print(labels)

  # Get dominant colors (image propeterties)
  output["colors"] = analyze_color(get_main_color(image))

  # Check required item scores
  required_items = ["Plant"]
  required_items_score = 0

  detected_labels = [x.description for x in labels if x.score > 0.3]

  for item in required_items:
    if item in output["objects"] or item in detected_labels:
      required_items_score = required_items_score + 1 / len(required_items)
      output["scoring"]["required_objects"][item] = True
    else:
      output["scoring"]["required_objects"][item] = False

  output["scoring"]["required_objects"]["score"] = required_items_score

  # Check room color score
  color_score = 1 if room_type in output["colors"]["rooms"] else 0

  output["scoring"]["color"]["score"] = color_score
  
  # Lightness required to get a 100%
  wanted_lightness = 80

  # Check lightness score
  rgb = tuple(int(output["colors"]["color"][i:i + 2], 16) for i in (0, 2, 4))

  lightness = colorsys.rgb_to_hls(rgb[0], rgb[1], rgb[2])[2]

  lightness_score = min(lightness / wanted_lightness, 1)
  lightness_score = max(lightness_score, 0)
  
  output["scoring"]["lighting"]["score"] = lightness_score

  output["scoring"][
    "total"] = required_items_score * 0.50 + color_score * 0.4 + lightness_score * 0.10

  # Reccomend a plant if it is a bright room with no plants
  if (lightness >= 60 and "Plant" not in output["objects"]):
    output["recommendations"].append("A plant can be a great addition to a room as it can help purify the air, add color and texture, and create a sense of calm.")

  # Recccomend a lamp if the room is dark
  if (lightness <= 30 and "Lighting" not in output["objects"]) and output["scoring"]["total"] < 0.7:
    output["recommendations"].append("Adding a lamp to a dark room can significantly improve the overall ambiance and functionality of the space by providing additional lighting and reducing eye strain.")

  # Reccomend a change of paint if it does not suite the room type
  if (color_score != 1):
    better_colors = [color["name"] for color in colors if room_type in color["rooms"]]
    if (len(better_colors) == 0):
      output["recommendations"].append("Consider repainting the walls to better match the inteded mood.")
    elif (len(better_colors) == 1):
      output["recommendations"].append("Consider repainting the walls to " + better_colors[0])
    else:
      output["recommendations"].append("Consider repainting the walls to be " + ", ".join(better_colors[:-1]) + ", or " + better_colors[-1])

  print(output)
  
  return json.dumps(output)

@app.route("/url", methods=["POST"])
def url():
  request_json = requests.get(request.args[0]).json()

  imgdata = base64.b64decode(request_json["image"])
  room_type = request_json["room_type"]

  output = {
    "objects": [],
    "colors": [],
    "scoring": {
      "required_objects": {
        "score": 0,
      },
      "color": {
        "score": 0
      },
      "lighting": {
        "score": 0
      }
    },
    "recommendations": []
  }

  # Get google api image
  image = vision.Image(content=imgdata)

  # Request object detection
  objects = vision_client.object_localization(
    image=image).localized_object_annotations

  print("Number of objects found: {}".format(len(objects)))
  for object_ in objects:
    print("\n{} (confidence: {})".format(object_.name, object_.score))
    if object_.score >= 0.5:
      if object_.name not in output["objects"]:
        output["objects"].append(object_.name)

  # Get dominant colors (image propeterties)
  output["colors"] = analyze_color(get_main_color(image))

  # Check required item scores
  required_items = ["Plant", "Lighting"]
  required_items_score = 0

  for item in required_items:
    if item in output["objects"]:
      required_items_score = required_items_score + 1 / len(required_items)
      output["scoring"]["required_objects"][item] = True
    else:
      output["scoring"]["required_objects"][item] = False

  output["scoring"]["required_objects"]["score"] = required_items_score

  # Check room color score
  color_score = 1 if room_type in output["colors"]["rooms"] else 0

  output["scoring"]["color"]["score"] = color_score
  
  # Lightness required to get a 100%
  wanted_lightness = 80


  # Check lightness score
  rgb = tuple(int(output["colors"]["color"][i:i + 2], 16) for i in (0, 2, 4))

  lightness = colorsys.rgb_to_hls(rgb[0], rgb[1], rgb[2])[2]

  lightness_score = min(lightness / wanted_lightness, 1)
  output["scoring"]["lighting"]["score"] = lightness_score

  output["scoring"][
    "total"] = required_items_score * 0.30 + color_score * 0.2 + lightness_score * 0.50

  # Reccomend a plant if it is a bright room with no plants
  if (lightness >= 60 and "Plant" not in output["objects"]):
    output["recommendations"].append("A plant can be a great addition to a room as it can help purify the air, add color and texture, and create a sense of calm.")

  # Recccomend a lamp if the room is dark
  if (lightness <= 30 and "Lighting" not in output["objects"]):
    output["recommendations"].append("Adding a lamp to a dark room can significantly improve the overall ambiance and functionality of the space by providing additional lighting and reducing eye strain.")

  # Reccomend a change of paint if it does not suite the room type
  if (color_score != 1):
    better_colors = [color["name"] for color in colors if room_type in color["rooms"]]
    if (len(better_colors) == 0):
      output["recommendations"].append("Consider repainting the walls to better match the inteded mood.")
    elif (len(better_colors) == 1):
      output["recommendations"].append("Consider repainting the walls to " + better_colors[0])
    else:
      output["recommendations"].append("Consider repainting the walls to be " + (", ".join(better_colors[:-1]))) + ", or " + better_colors[-1]

  print(output)
  
  return json.dumps(output)

def get_main_color(image):
  response = vision_client.image_properties(image=image)
  props = response.image_properties_annotation

  print(response)

  main_color = props.dominant_colors.colors[0].color

  main_rgb = (int(main_color.red), int(main_color.green), int(main_color.blue))
  

  return main_rgb


def analyze_color(color_a):
  distances = []

  for color in colors:
    h = color["color"]
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    dist = color_distance(color_a, rgb)

    distances.append(dist)

  minindex = distances.index(min(distances))

  output_data = colors[minindex]

  output_data["color"] = str('%02x%02x%02x' % color_a)

  return output_data


def color_distance(e1, e2):
  rmean = int((e1[0]) + int(e2[0])) // 2
  r = int(e1[0]) - int(e2[0])
  g = int(e1[1]) - int(e2[1])
  b = int(e1[2]) - int(e2[2])
  return math.sqrt((int((512 + rmean) * r * r) >> 8) + 4 * g * g +
                   (((767 - rmean) * b * b) >> 8))

print(analyze_color((255, 100, 255)))

app.run(host="0.0.0.0", port=80)
