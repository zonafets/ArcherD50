#!/usr/bin/env python3

""" utility to read informations from TP-Link router Archer D50 """

# from: https://community.openhab.org/t/creating-a-chart-based-on-tp-link-modem-statistics/28545/4

# Archer D50
# dev version: softwareVersion=0.8.0 1.3 v0046.0 Build 170223 Rel.61663n
# Firmware Version:0.8.0 1.3 v0046.0 Build 170223 Rel.61663n Hardware Version:Archer D50 v1 00000000 

import os
import sys
import urllib.request
import json
import ipaddress
import time
from influxdb import InfluxDBClient
import datetime
import threading
from threading import Timer
import base64
import itertools
from datetime import datetime

#########################################################################################

router_ip = ""
router_pwd = ""
pwdbase64 = ""

#########################################################################################

def encodePwd(pwd):
  pwd_bytes = pwd.encode('ascii')
  base64_bytes = base64.b64encode(pwd_bytes)
  base64_message = base64_bytes.decode('ascii')
  return base64_message

#########################################################################################

def readData(cmd,payload):
  global pwdbase64
  if router_pwd == '': raise ValueError("No password given")
  if pwdbase64 == "":
    pwdbase64 = encodePwd(router_pwd)

  retry = 3
  rsp=b''
  lines = []
  while retry>0 and rsp==b'':
    try:
      url = 'http://'+router_ip+'/cgi?'+cmd
      params = payload
      params = params.encode('utf8')
      post_fields = {
        'Referer': 'http://'+router_ip+'/',
        'Cookie':'Authorization=Basic '+pwdbase64,
        'Content-Type': 'text/plain; charset=UTF-8'
      }

      request = urllib.request.Request(url, data=params, headers=post_fields)
      response = urllib.request.urlopen(request)

      rsp = response.read()
      if rsp!=b'':
        response_txt = rsp.decode('utf8')
      # sometimes happen this error:
      # UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa4 in position 3454: invalid start byte


        lines = response_txt.splitlines()
        if len(lines)>0 and not "500:" in lines[0]: break

    except:
      print("Unexpected error:", sys.exc_info()[0])

    finally:
      if rsp==b'': retry -= 1

  if retry == 0: raise BaseException("Connection error")

  #for line in lines:
  #  if line.startswith("[error]")

  return lines

#########################################################################################

def resetStatistics():
  return readData("2","[STAT_CFG#0,0,0,0,0,0#0,0,0,0,0,0]0,1\r\naction=2\r\n")

#########################################################################################

def clients():

  lines = readData("5","[LAN_HOST_ENTRY#0,0,0,0,0,0#0,0,0,0,0,0]0,0\r\n")

  # read hosts from router

  dev = {}
  devs = []
  for line in lines:
    words = line.split('=')
    if line.startswith('['):
      if dev!={}:
        devs.append(dev)
        dev={}
    if words[0]=='MACAddress': dev['mac']=words[1]
    if words[0]=='hostName': dev['host']=words[1]
    if words[0]=='active': dev['active']=int(words[1])

  clients = {}
  for dev in devs:
    mac = dev["mac"]
    if dev["host"] == "Unknown": dev["host"] = mac
    clients[mac]={"host":dev["host"],"active":dev["active"]}

  return clients

#########################################################################################

def mixAndSaveHosts(devs,filePath):

  # this def records historically mac addresses and names

  # load from disk

  if os.path.exists(filePath):
    with open(filePath, 'r') as fc:
      config = json.load(fc)
  else:
      config = {"names":{},"hosts":{}}

  # mix
  names = config["names"]
  hosts = config["hosts"]
  for mac in devs:
    dev = devs[mac]
    host = hosts.get(mac, '')
    if host == '':
      hosts[mac] = dev
      names[dev["host"]] = dev["host"]

  #save to disk

  json_data = json.dumps(config, ensure_ascii=False, indent=4)
  with open(filePath, 'w') as f:
    f.write (json_data)

  return config


#########################################################################################

def statistics():

  # the data change every N seconds depending from interval value
  # byte a totalBytes and packets change every getData

  lines = readData("1&5","[STAT_CFG#0,0,0,0,0,0#0,0,0,0,0,0]0,0\r\n[STAT_ENTRY#0,0,0,0,0,0#0,0,0,0,0,0]1,0\r\n")

  interval = enable = 0
  stat={}
  stats=[]
  for line in lines:
    words = line.split('=')
    if line.startswith('['):
      if stat!={}:
        stats.append(stat)
        stat={}
    if words[0]=='ipAddress': stat['ipAddress'] = str(ipaddress.IPv4Address(int(words[1])))
    if words[0]=='macAddress': stat['macAddress']=words[1]
    if words[0]=='totalBytes': stat['totalBytes']=int(words[1])
    if words[0]=='currBytes': stat['currBytes']=int(words[1])
    if words[0]=='totalPkts': stat['totalPkts']=int(words[1])
    if words[0]=='currIcmp': stat['currIcmp']=int(words[1])
    if words[0]=='currUdp': stat['currUdp']=int(words[1])
    if words[0]=='currSyn': stat['currSyn']=int(words[1])
    if words[0]=='interval': interval=int(words[1])
    if words[0]=='enable': enable=int(words[1])

  # group by mac address

  data={}
  for stat in stats:
    mac = stat["macAddress"]
    if mac in data:
      dev = data[mac]
      dev["totalBytes"]+=stat["totalBytes"]
      dev["totalPkts"]+=stat["totalPkts"]
      dev["ipAddress"]+=","+stat["ipAddress"]
    else:
      data[mac]={
        "totalBytes": stat["totalBytes"],
        "totalPkts": stat["totalPkts"],
        "currBytes": stat["currBytes"],
        "currIcmp": stat["currIcmp"],
        "currUdp": stat["currUdp"],
        "currSyn": stat["currSyn"],
        "ipAddress": stat["ipAddress"],
      }

  enabled = False
  if enable == 1: enabled = True
  return {"interval":interval,"enabled":enabled,"data":data}

#########################################################################################

if __name__ == '__main__':

  print(sys.argv[0]," set of utilities to read info from TP-Link Archer D50 router")
  print("")
  quit()

