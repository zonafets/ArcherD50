#!/usr/bin/env python3

import os
import sys
import json
import time
from influxdb import InfluxDBClient
import datetime
import threading
from threading import Timer
from datetime import datetime
import ntpath
import ArcherD50

#########################################################################################

log = False
trace = False

file_hosts = "hosts.json"
db3y = "netusage3y"
db3d = "netusage3d"
db1h = "netusage1h"

#########################################################################################

def db_open(drop=False):

  """ open/create databases """

  client = InfluxDBClient(host='localhost', port=8086)
  # client.create_database('netusage')
  # client.get_list_database()
  # [{'name': '_internal'}, {'name': 'netusage'}]
  # dbs = client.get_list_database()
  # if netusage not in dbs:
  if drop==True:
    client.drop_database(db3y)
    client.drop_database(db3d)
    client.drop_database(db1h)


  # the following two doesn't works
  #client.create_retention_policy('awesome_policy', '3d', 3, default=True)
  #create_retention_policy(name, duration, replication, database=None, default=False, shard_duration=u'0s')

  print("Create databases ", db3y, db3d, db1h )
  client.create_database(db3y)
  client.create_database(db3d)
  client.create_database(db1h)

  print("Create a retention policy")

  client.create_retention_policy(
    name="3y",
    duration="1095d",
    replication=1,
    database=db3y,
    default=False,
    shard_duration=u'0s')

  client.create_retention_policy(
    name="3d",
    duration="3d",
    replication=1,
    database=db3d,
    default=False,
    shard_duration=u'0s')

  client.create_retention_policy(
    name="1h",
    duration="1h",
    replication=1,
    database=db1h,
    default=False,
    shard_duration=u'0s')

  return client 

#########################################################################################

def db_rename_tag(oldTag,newTag):

  """ todo: rename tags of unk hosts (mac address only) with new name given with hosts.json """

  print("todo")
  # see also SELECT INTO
  #async with aioinflux.InfluxDBClient(host='influxdb', db='mydb', output='dataframe') as client:
  #  df = await client.query("SELECT host as host2,* FROM measurement")
  #  delete df['host']
  #  await client.write(df, measurement="measurement_new", tag_columns=["host2"])

#########################################################################################

def MbitsXsecs(bytes,intervalSecs):

  """Convert bytes x interval into megabits x seconds"""

  return round(bytes*8.0/1000000.0/intervalSecs,4)

#########################################################################################

def db_save60s(params):

  """Save data every 60secs for 3 days statistics """

  client = params["client"]

  hostsData = params["hostsData"]
  if len(hostsData) == 0: return

  time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

  for host in hostsData:
    data = hostsData[host]
    pktsize = 0
    bytes = data["bytes"]
    cbytes = data["cbytes"]
    if data["pkts"]>0: pktsize = int(bytes/data["pkts"])
    txPkts = (data["icmp"]+data["udp"]+data["syn"])
    if bytes>0 or txPkts>0:
      # none of this works:
      # txBytes = pktsize * data["udp"]
      # txBytes = 1500 * txPkts
      # txBytes = 1500 * data["udp"]
      # rxBytes = data["bytes"] - txBytes
      # if rxBytes<0: print("rx negative")
      json = [
         {
            "measurement": "ArcherD50."+host,
            # this doesn't show well in chronograf
            #"tags": {
            #   "host": host,
            #},
            "time": time,
            "fields": {
                "mac": data["mac"],
                "Bps": round(bytes/60.0,4),
                #"cMBps": MbitsXsecs(cbytes,60.0),
                #"Pkts": dat["pkts"],
                #"RxMBps": rxBytes/60*1000,
                #"TxMBps": txBytes/60*1000,
                #"PktSize": pktsize,
                #"ICmpPkts": data["icmp"],
                #"UdpPkts": data["udp"],
                #"SynPkts": data["syn"],
                "TxPkts": txPkts,
                "ipAddresses": data["ip"]
            }
        }
      ]

      client.switch_database(db3d)
      client.write_points(json,time_precision='m',retention_policy="3d")

      json = []

#########################################################################################

def db_save10s(params):

  """Save data every "interval" (normally 10secs) to quickly see who is eating band"""

  client = params["client"]

  hosts = params["hosts"]["hosts"]
  names = params["hosts"]["names"]

  interval = params["hostsData"]["interval"]
  hostsData = params["hostsData"]["data"]
  if len(hostsData) == 0: return

  time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

  json = [
    {
          "measurement": "ArcherD50",
          #"tags": {
          #   "host": "all",  # all known hosts
          #},
          "time": time,
          "fields": {}
    }
  ]

  fields = json[0]["fields"]

  for mac in hosts:
    if mac in hostsData:

      data = hostsData[mac]
      # bytes read in interval seconds converted in MegaBits/s

      host = hosts[mac]["host"]
      if host in names: host = names[host]

      mbits = MbitsXsecs(data["currBytes"],interval)
      #if not host in fields: fields[host]={"MBits":0}
      fields[host] = mbits


  client.switch_database(db1h)
  client.write_points(json,time_precision='s',retention_policy="1h")

  json = []

#########################################################################################

def collectStatistics(data, current, previous, clients):

  """ collect data every read """

  # diffs the total params and adds the curr params

  hosts = clients["hosts"]
  names = clients["names"]

  cdata = current["data"]
  pdata = previous["data"]

  # scan all known and new hosts
  for mac in hosts:

    cbytes = bytes = pkts = icmp = udp = syn = 0
    ip = ""

    pfound = cfound = False

    if mac in cdata and mac in pdata:
      cdev = cdata[mac]
      pdev = pdata[mac]

    if mac in cdata:
      pfound = True
      cdev = cdata[mac]
      bytes += cdev["totalBytes"]
      pkts += cdev["totalPkts"]
      cbytes += cdev["currBytes"]
      icmp += cdev["currIcmp"]
      udp += cdev["currUdp"]
      syn += cdev["currSyn"]
      ip += cdev["ipAddress"]

    if mac in pdata:
      cfound = True
      pdev = pdata[mac]
      bytes -= pdev["totalBytes"]
      pkts -= pdev["totalPkts"]
      if bytes<0:
        bytes = 0
        pkts = 0
      icmp += pdev["currIcmp"]
      udp += pdev["currUdp"]
      syn += pdev["currSyn"]
      cbytes += pdev["currBytes"]
      if not ip in pdev["ipAddress"]: ip+=","+pdev["ipAddress"]

    if bytes>0 or icmp+udp+syn>0 or cbytes>0:
      host = hosts[mac]["host"]
      if host in names: host = names[host]

      if not host in data:
        dat = data[host] = {}
        dat["mac"] = mac
        dat["bytes"] = 0
        dat["cbytes"] = 0
        dat["pkts"] = 0
        dat["icmp"] = 0
        dat["udp"] = 0
        dat["syn"] = 0
        dat["ip"] = ""
      else:
        dat = data[host]
        if not mac in dat["mac"]: dat["mac"]+=","+mac

      dat["bytes"] += bytes
      dat["cbytes"] += cbytes
      dat["pkts"] += pkts
      dat["icmp"] += icmp
      dat["udp"] += udp
      dat["syn"] += syn
      dat["ip"] = ip

  previous["data"] = current["data"]
  return data

#########################################################################################

def collect(db_client = None):

  """ collect data every 10,60 seconds and 1 day (to do) """

  while True:

    try:
      interval = 0
      enabled = False

      print("# wait until statistics are enabled")
      while True:
        stat = ArcherD50.statistics()
        interval = stat["interval"]
        enabled = stat["enabled"]
        if enabled == True: break
        time.sleep(interval)

      print("# reset")
      ArcherD50.resetStatistics()

      print("# get base statistics")
      previousData = ArcherD50.statistics()

      originalInterval = interval = previousData["interval"]
      enabled = previousData["enabled"]

      def waitSync():
        # sync at the :00 seconds
        # maybe a better sync must be based on change of statistics
        # but we cannot know when bencause totalbytes change every read
        # while currentbytes can be same value between previous and current interval
        while datetime.now().second % interval != interval-1:
          # print("Waiting perfect minute:",datetime.now().second)
          time.sleep(1)

      def singleSep():
          print('-'*132)

      def doubleSep():
          print('='*132)

      print("# wait interval sync")
      waitSync()
      totInterval = 0

      print("# interval:",interval," enable:",enabled)

      data = {}

      print("# collecting")

      while True:

        starttime = time.time()

        devices = ArcherD50.clients()
        hosts = ArcherD50.mixAndSaveHosts( devices, file_hosts )
        currentData = ArcherD50.statistics()

        interval = currentData["interval"]
        enabled = currentData["enabled"]
        if enabled == False or interval != originalInterval:
          # if disabled or capture time is changed, we must restart
          break

        data = collectStatistics(data,currentData,previousData,hosts)

        dtnow = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        if log:
          for host in data:
            dat = data[host]
            mac = dat["mac"]
            bytes = dat["bytes"]
            cbytes = dat["cbytes"]
            pkts = dat["pkts"]
            icmp = dat["icmp"]
            udp = dat["udp"]
            syn = dat["syn"]
            ip = dat["ip"]
            print(
             "%20s %30s %40s %10d %5d %5d %5d %s" % (
               dtnow,host,mac,bytes,icmp,udp,syn,ip
             )
            )

        if db_client != None:
          db_save10s({"client":db_client,"hostsData":currentData, "hosts":hosts})

        totInterval+=interval
        if totInterval>=60:
          if db_client != None:
            if trace: print(dtnow," db registration")
            db_save60s({"client":db_client,"hostsData":data})
          totInterval = 0
          data = {}
          if log: doubleSep()
        else:
          if log: singleSep()

        # this method is not perfect
        # time.sleep(interval - ((time.time() - starttime) % interval))

        waitSync()

    except KeyboardInterrupt:
      quit()

    except:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
      print(exc_type, fname, exc_tb.tb_lineno)
      # pass
      raise

  # while

#########################################################################################

def test():
  log = True
  collect()

#########################################################################################

if __name__ == '__main__':

  config = '/etc/'+ntpath.splitext(ntpath.basename(sys.argv[0]))[0]+'.conf'

  if len(sys.argv) == 1:

    print(sys.argv[0],"read statistics from TP-Link Archer D50 router and save into influxDB")
    print("")
    print("   A config file is required in ",config," of json format:")
    print("     {router-ip:A.B.C.D, password: your_router_password}")
    print("")
    print("Arguments:")
    print("")
    print("   dropdb  delete and recreate the database")
    print("   log     log every statistics")
    print("   run     start to collect statistics")
    print("")
    quit()

  if not os.path.exists(config):
    print("Config file '%s' not found" % (config))
    quit()

  with open(config, 'r') as fc:
    config_json = json.load(fc)

  ArcherD50.router_ip = config_json["router_ip"]
  ArcherD50.router_pwd = config_json["router_pwd"]

  drop = False
  if "dropdb" in sys.argv: drop = True
  if "log" in sys.argv: log = True
  if "trace" in sys.argv: trace = True
  if "run" in sys.argv: collect(db_open(drop))
