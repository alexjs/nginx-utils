#!/usr/bin/python
'''A daemon which parses nginx configs, and
    checks to see whether the IPs of any backend nodes have changed.
'''

import socket
import time
import re
import hashlib
import os
import argparse
import sys
import subprocess
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

# Default configs (may be overriden by script parameters)
nginxInitScript = "/etc/init.d/nginx"
nginxConfigDir = "/etc/nginx/sites-enabled"
checkTime = 3600


# Parse our args
parser = argparse.ArgumentParser(prog='watcher.py',
    description='''A daemon which parses nginx configs, and
    checks to see whether the IPs of any backend nodes have changed.
    ''')
parser.add_argument('-d', '--directory', nargs=1, 
    help='Directory to grab configs from', 
    metavar='nginxConfigDir')
parser.add_argument('-t', '--time', nargs=1,
    type=int,
    help='Seconds to wait between checks', 
    metavar='checkTime')
parser.add_argument('-i', '--init-script', nargs=1,
    type=str,
    help='Location of init script (defaults to /etc/init.d/nginx)')
parser.add_argument('-n', '--dry-run', action='store_true',
    help='Whether to restart nginx or merely alert about it')
parser.add_argument('-v', '--verbose', action='store_true',
    help='Verbosity level')
params = parser.parse_args()

dryRun = params.dry_run
verbose = params.verbose

if verbose:
    def verboseprint(*args):
        ''' Print each argument separately so caller doesn't need to
        stuff everything to be printed into a single string '''
        for arg in args:
            print arg,
        print
else:   
    verboseprint = lambda *a: None  

if params.directory:
    nginxConfigDir = params.directory[0]
    verboseprint("Using directory " + nginxConfigDir)
if params.time:
    checkTime = params.time[0]
    verboseprint("Using time interval " + str(checkTime))
if params.init_script:
    nginxInitScript = params.init_script[0]
    verboseprint("Using init script " + nginxInitScript)

# Main
# Preset variables
configHash = defaultdict()
matches = []
oldaddress = defaultdict(list)
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
            # Skipping, hidden file
            verboseprint("Skipping hidden file:", 
                    nginxConfigDir + nginxConfigFile)
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
                    verboseprint("New checksum detected for file", 
                            nginxConfigFilePath, 
                            "- updating dict")
                    matches = parse_file(nginxConfigFilePath)
                    # Update the dict to include the new file
                    configHash[nginxConfigFile] = checksum
            else:
                # Parse the file for the first time
                matches += parse_file(nginxConfigFilePath)
                verboseprint("New config file detected -", 
                        nginxConfigFilePath, 
                        "- updating dict")
                # Update the dict to include the new file
                configHash[nginxConfigFile] = checksum

    # Iterate over our matches, but only if we haven't restarted in this loop
    hasRestarted = False
    for match in matches:
        if hasRestarted == False:
            # Isolate the hostname
            hostname = re.sub(r'.* (.*):.* .*', r'\1', match)
            # grab the address range
            addr = socket.getaddrinfo(hostname, None)     
            if addr != oldaddress[hostname]:
                verboseprint("Evaluating hostname", hostname)
                if firstRun == False and dryRun == False:
                    verboseprint("Backend has changed IP. Bouncing nginx")
                    restart = subprocess.call([
                        nginxInitScript, 
                        "restart"])
                    if restart == 0:
                        verboseprint("Nginx restart returned with 0 exit code")
                        hasRestarted = True
                    else:
                        sys.stderr.write(
                                "Nginx failed to restart. Loop continuing \n")
            else:
                verboseprint("No change to hostname", hostname)
            oldaddress[hostname] = addr
    firstRun = False
    verboseprint("Sleeping for " + str(checkTime) + " seconds")
    time.sleep(checkTime)
