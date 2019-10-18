#!/usr/bin/python3

from db_ingest import DBIngest
from db_query import DBQuery
from signal import signal, SIGTERM
from concurrent.futures import ThreadPoolExecutor
from rec2db import Rec2DB
#from runva import RunVA
import os
import time
import datetime
import random
import uuid

office = list(map(float, os.environ["OFFICE"].split(",")))
dbhost = os.environ["DBHOST"]
every_nth_frame = int(os.environ["EVERY_NTH_FRAME"])

rec2db=None
#runva=None
stop=False

def connect(sensor, algorithm, uri):
    db=DBIngest(host=dbhost, index="algorithms",office=office)
    db.update(algorithm["_id"], {
        "sensor": sensor["_id"],
    })
    db=DBIngest(host=dbhost, index="analytics", office=office)
    while not stop:
        counts=[]
        for i in range(60):
            counts.append({
                "time": int(time.mktime(datetime.datetime.now().timetuple())*1000+i*33.333),
                "office": {
                    "lat": office[0],
                    "lon": office[1],
                },
                "sensor": sensor["_id"],
                "location": sensor["_source"]["location"],
                "algorithm": algorithm["_id"],
                "count": {
                    "people": int(random.random()*1000),
                },
            })
        db.ingest_bulk(counts)
        time.sleep(2)

def quit_service(signum, sigframe):
    global stop
    stop=True
    if rec2db: rec2db.stop()
    #if runva: runva.stop()

signal(SIGTERM, quit_service)
dba=DBIngest(host=dbhost, index="algorithms", office=office)
dbs=DBQuery(host=dbhost, index="sensors", office=office)

# register algorithm (while waiting for db to startup)
while not stop:
    try:
        algorithm=dba.ingest({
            "name": "people-counting",
            "office": {
                "lat": office[0],
                "lon": office[1],
            },
            "status": "processing",
            "skip": every_nth_frame,
        })
        break
    except Exception as e:
        print("Exception: "+str(e), flush=True)
        time.sleep(10)

# compete for a sensor connection
while not stop:
    try:
        print("Searching...", flush=True)
        for sensor in dbs.search("sensor:'camera' and status:'idle' and algorithm='people-counting' and office:["+str(office[0])+","+str(office[1])+"]"):
            try:
                # compete (with other va instances) for a sensor
                r=dbs.update(sensor["_id"],{"status":"streaming"},version=sensor["_version"])

                # stream from the sensor
                print("Connected to "+sensor["_id"]+"...",flush=True)
                connect(sensor,algorithm,sensor["_source"]["url"])

                # if exit, there is somehting wrong
                r=dbs.update(sensor["_id"],{"status":"disconnected"})
                if stop: break

            except Exception as e:
                print("Exception: "+str(e), flush=True)

    except Exception as e:
        print("Exception: "+str(e), flush=True)

    time.sleep(10)

# delete the algorithm instance
dba.delete(algorithm["_id"])

