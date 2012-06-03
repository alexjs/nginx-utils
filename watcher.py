#!/usr/bin/python
import socket
import time
import pprint
import re
import hashlib
import os
import argparse
import sys
from collections import defaultdict


def md5_checksum(file_path):
    ''' Return an md5sum for a given file
    but only load in 8k blocks to avoid memory issues'''
    fh = open(file_path, 'rb')
    m = hashlib.md5()
    while True:
        data = fh.read(8192)
        if not data:
            break
        m.update(data)
    return m.hexdigest()

def parse_file(file_name):
    ''' Parse the passed file for 'server' strings. This is 
    utterly utterly horrible '''
    config = open(file_name)
    configContents = config.read()
    config.close()
    __matches = re.findall(r"server.*:.* ", configContents)
    return __matches

pp = pprint.PrettyPrinter(indent=4)

# Default configs (may be overriden by script parameters)
nginxConfigDir = "/etc/nginx/sites-enabled"
checkTime = float(3600)


# Parse our args

parser = argparse.ArgumentParser(prog='watcher.py',
    description='''A daemon which parses nginx configs, and
    checks to see whether the IPs of any backend nodes have changed.
    ''')
parser.add_argument('-d', '--directory', nargs=1, 
    help='Directory to grab configs from', 
    metavar='nginxConfigDir')
parser.add_argument('-t', '--time', nargs=1,
    type=float,
    help='Seconds to wait between checks', 
    metavar='checkTime')

params = parser.parse_args()

if params.directory:
    nginxConfigDir = params.directory[0]

if params.time:
    checkTime = params.time[0]

# Main

# Preset variables
configHash = defaultdict()
matches = []
address =  defaultdict(list)
firstRun = True

# Loop
while True:
    try:
        dirList = os.listdir(nginxConfigDir)
    except os.error, err:
        sys.stderr.write("Directory " + 
            nginxConfigDir + 
            " does not exist. Skipping check on" +
            " this run. \n")
        dirList = []
    # Grab a list of all of our nginx configs
    # Iterate over them
    for nginxConfigFile in dirList:
        # Ignore hidden files
        if re.match('^\.', nginxConfigFile):
            #Skipping, hidden file
            pass
        else:
            # Get a full file path
            nginxConfigFilePath = nginxConfigDir + "/" + nginxConfigFile
            # Check the md5sum, and
            # only repopulate the lists if our md5sum changes
            checksum = md5_checksum(nginxConfigFilePath)
            # If we already have a hash for this configfile...
            if configHash.has_key(nginxConfigFile):
                # and if the hash we have doesn't match...
                if configHash[nginxConfigFile] != checksum:
                    matches = parse_file(nginxConfigFilePath)
                    # Update the dict to include the new file
                    configHash[nginxConfigFile] = checksum
            else:
                # Parse the file for the first time
                matches += parse_file(nginxConfigFilePath)
                # Update the dict to include the new file
                configHash[nginxConfigFile] = checksum

    # Iterate over our matches, but only if we haven't restarted in this loop
    hasRestarted = False
    for match in matches:
        if hasRestarted == False:
            # Isolate the hostname
            hostname = re.sub(r'.* (.*):.* .*', r'\1', match)
            # grab the address range, shove it in a dict
            address[hostname] = socket.getaddrinfo(hostname, None)     
            if address[hostname] != address[hostname + "old"]:
                if firstRun == False:
                    print "change"
                    #subprocess.call("/etc/init.d/nginx restart")
                    hasRestarted = True
                else:
                    pass              
            else:
                print "same"
            address[hostname + "old"] = address[hostname]
    firstRun = False
    print "Sleeping for " + str(checkTime) + " seconds"
    time.sleep(checkTime)
