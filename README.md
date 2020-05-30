# ArcherD50
Utility to get statistics and traffic monitoring from TP-Link Archer D50![chronograf](D:\Documents\develop\GitHub\ArcherD50\chronograf.png)

There are two modules:

- **ArcheD50.py** contain functions to communicate with the router
- **ArcherD50Statistics.py** uses ArcherD50 functions to collect data and store it into two databases of InfluxDB
  - the 1st DB keep 1h of data, updated every 10 seconds
  - the 2nd DB keep 3 days of data updated every 1 minute

Modify and copy **ArcherD50Statistics.conf** into **/etc**.

Unfortunately was not possible distinguish TX and RX. 

ICMP, UDP and SYN packets data are captured too.

### Todo

- add **snmp** functionality to read the whole tx/rx flux as PRTG was able to do with this model
- add internet speed test







