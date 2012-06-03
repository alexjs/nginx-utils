#!/usr/bin/python
import socket
import time
import pprint
import re
import hashlib
import os
import argparse
from collections import defaultdict


def md5Checksum(filePath):
    fh = open(filePath, 'rb')
    m = hashlib.md5()
    while True:
        data = fh.read(8192)
        if not data:
            break
        m.update(data)
    return m.hexdigest()

def parseFile(fileName):
    config = open(fileName)
    configContents = config.read()
    config.close()
    matches = re.findall(r"server.*:.* ", configContents)
    return matches

pp = pprint.PrettyPrinter(indent=4)

# Default configs (may be overriden by script parameters)
nginxConfigDir = "/etc/nginx/sites-enabled"


# Parse our args

parser = argparse.ArgumentParser(prog='watcher.py',
    description='''A daemon which parses nginx configs, and
    checks to see whether the IPs of any backend nodes changes.
    ''')
parser.add_argument('-d', '--directory', nargs=1, help='Directory to grab configs from', metavar='nginxConfigDir')

params = parser.parse_args()

if params.directory != '':
    nginxConfigDir = params.directory[0]

# Main

# Preset variables
configHash = defaultdict()
matches = []
address =  defaultdict(list)
firstRun = True


# Loop

while True:
    # Grab a list of all of our nginx configs
    dirList = os.listdir(nginxConfigDir)
    # Iterate over them
    for nginxConfigFile in dirList:
        # Ignore hidden files
        if re.match('^\.', nginxConfigFile):
            #Skipping, hidden file
            pass
        else:
            # Get a full file path
            nginxConfigFilePath = nginxConfigDir + "/" + nginxConfigFile
            # Check the md5sum, and only repopulate the lists if our md5sum changes
            checksum = md5Checksum(nginxConfigFilePath)
            # If we already have a hash for this configfile...
            if configHash.has_key(nginxConfigFile):
                # and if the hash we have doesn't match...
                if configHash[nginxConfigFile] != checksum:
                    matches = parseFile(nginxConfigFilePath)
                    # Update the dict to include the new file
                    configHash[nginxConfigFile] = checksum
            else:
                # Parse the file for the first time
                matches += parseFile(nginxConfigFilePath)
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
                    print "Not changing, first iteration"                
            else:
                print "same"
            address[hostname + "old"] = address[hostname]
    firstRun = False
    time.sleep(3600)