#!/usr/bin/python3

from db_ingest import DBIngest
import requests
import time
import os
import json

dbhost=os.environ["DBHOST"]
office=list(map(float,os.environ["OFFICE"].split(",")))
proxyhost=os.environ["PROXYHOST"]
scenario=os.environ["SCENARIO"]
zone=os.environ["ZONE"]

_include_type_name={"include_type_name":"false"}
officestr='$'+('$'.join(map(str,office)))
settings={
    "offices": {
        "settings": {
            "index.routing.allocation.include.zone": "cloud",
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
        },
        "mappings": {
            "properties": {
                "location": { "type": "geo_point", },
            },
        },
    },
    "recordings_c": {
        "settings": {
            "index.routing.allocation.include.zone": "cloud",
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
        },
        "mappings": {
            "properties": {
                "office": { "type": "geo_point", },
            },
        },
    },
    "provisions"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "location": { "type": "geo_point", },
            },
        },
    },
    "sensors"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "office": { "type": "geo_point", },
                "location": { "type": "geo_point", },
                "ip": { "type": "ip", },
            },
        },
    },
    "recordings"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "office": { "type": "geo_point" },
                "time": { "type": "date" },
                "streams": { "type": "nested" },
            },
        },
    },
    "algorithms"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "office": { "type": "geo_point" },
            },
        },
    },
    "analytics"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "office": { "type": "geo_point" },
                "location": { "type": "geo_point" },
                "time": { "type": "date" },
                "objects": { "type": "nested" },
            },
        },
    },
    "alerts"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "time": { "type": "date" },
                "location": { "type": "geo_point" },
                "office": { "type": "geo_point" },
            },
        },
    },
    "services"+officestr: {
        "settings": {
            "index.routing.allocation.include.zone": "cloud,"+zone,
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
            },
        },
        "mappings": {
            "properties": {
                "office": { "type": "geo_point" },
            },
        },
    },
}

# wait for db
while True:
    try: 
        r=requests.get(dbhost)
        break
    except:
        print("Waiting for DB...", flush=True)
        time.sleep(1)

# delete sensors, provisions, algorithms, and services. 
for index in ["sensors","provisions","algorithms","services"]:
    requests.delete(dbhost+"/"+index+officestr)

# initialize db index settings
routing_key="index.routing.allocation.include.zone"
for index in settings:
    routing_value=settings[index]["settings"].pop(routing_key)
    requests.put(dbhost+"/"+index,json=settings[index],params=_include_type_name)
    requests.put(dbhost+"/"+index+"/_settings",json={ routing_key: routing_value })

# populate db with simulated offices and provisions
with open("/run/secrets/sensor-info.json",encoding='utf-8') as fd:
    data=json.load(fd)
    dbo=DBIngest(index="offices",office="",host=dbhost)
    dbp=DBIngest(index="provisions", office=office, host=dbhost)
    for office1 in data:
        if scenario != office1["scenario"]: continue
        location1=office1["location"]
        if location1["lat"]!=office[0] or location1["lon"]!=office[1]: continue
        office1.pop("scenario")

        sensors=office1.pop("sensors")
        office1["uri"]=proxyhost
        office1["zone"]=zone
        dbo.ingest(office1,officestr[1:])

        for s in sensors: s["office"]=location1
        dbp.ingest_bulk(sensors)

print("DB Initialized", flush=True)

