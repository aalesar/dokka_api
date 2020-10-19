from flask import Flask
from flask import Response
from flask import stream_with_context
from flask import request
import werkzeug.wsgi
from flask_mongoengine import MongoEngine
from mongoengine import *
from geopy.distance import distance as geo_distance
from geopy import geocoders
import requests
import json
import sys



app = Flask(__name__)
app.config['MONGODB_SETTINGS'] = {
    'db': 'georesults',
    'host': 'localhost',
    'port': 27017
}
db = MongoEngine()
db.init_app(app)

class Point(EmbeddedDocument):
    name = StringField(required=True)
    address = StringField(required=True)
    geolocation = PointField(required=True)

    def to_json(self):
        return {"name": self.name,
                "address": self.address}

class Link(EmbeddedDocument):
    name = StringField(required=True)
    distance = StringField(required=True)
    
class Result(Document):
    point = EmbeddedDocumentListField(Point)
    link = EmbeddedDocumentListField(Link)

    def to_json(self):
        return {"points": [point.to_json() for point in self.point],
                "links": [link.to_json() for link in self.link],
                "result_id": str(self.pk)}

def get_geo_address_arcGIS(lat, long, langcode="EN", out_sr="",for_storage="false",output_format="pjson"):
    """Returns geoaddress by lattitude longtitude coordinates
        from ArcGiS api"""

    geo_url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode"
    payload = {
        "location":lat + " , " + long,
        "outSR" :out_sr,
        "langCode":langcode,
        "forStorage":for_storage,
        "f":output_format   
        }
    try:
        response = requests.get(geo_url, params=payload)
        js_resp = json.loads(response.text)
    except Exception as e:
        print(e)# logging
        raise Exception
    else:
        return js_resp["address"]["LongLabel"]

    


@app.route("/getAddresses", methods=["POST"])
def get_addresses():
    result = Result()
    result.save()
    lines_gen = werkzeug.wsgi.make_line_iter(request.stream)
    for line in lines_gen:
        point_name, lat, long = str(line,"utf-8").split(",")
        point_address = ""
        try:
            point_address = get_geo_address_arcGIS(lat, long)
        except:
            point_address = "Unknown address"
        for point in result.point:
            distance = geo_distance(point.geolocation,(lat, long)).meters
            result.link.append(Link(name=point_name+point.name, distance=str(distance)))
        result.point.append(Point(name=point_name, address = point_address, geolocation = (float(lat),float(long))))
        result.save()

    return result.to_json() , 200


@app.route("/getResult/<result_id>", methods=["GET"])
def get_result(result_id=None):
    if not result_id:
        return "Please provide result_id", 400
    result = Result.objects(pk=result_id).first()
    if result:
        return result.to_json() , 200
    return "No such result id exists", 404

