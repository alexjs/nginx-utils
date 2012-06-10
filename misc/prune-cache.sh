#!/bin/bash
#
# prune-cache.sh:
#
# Prune directories based on last access time
#
# Useful if you're using nginx with proxy_store - which doesn't allow you
# to set up a 'use only this much disk'
# 
# Since our file population and fetching method updates atime, delete files 
# based on that.
# 
# Keep pruning back increasing by a day at a time until we hit our min. 
# Alert if it breaches a threshold
# 
# More-or-less relies on a dedicated filesystem for pruning.


# Config Vars
pruneDir="/Volumes/ramdisk/cache"
pruneAge="30"
minPruneAge="7"
maxDisk="95"
alertEmail="alex@alexsmith.org"

# Config Consts
HOSTNAME=$(hostname)

# Funcs 
checkVars() {    
    if [[ -z "${alertEmail}" ]]; then
        echo "Please set an email address for alerts"
        exit 1
    fi
    
    if [[ -z "{pruneDir}" ]]; then
        echo "Please set a directory to prune"
        exit 1
    fi
}

checkDisk() {
    local diskSpace=$(df -h $1 | tail -n1 | awk '{sub(/%/, ""); print $5}')
    if [[ ${?} == "0" ]]; then
        echo ${diskSpace}
    else
        echo "Error checking disk space"
        exit 1
    fi
}

grabFiles() {
    local fileList=$(find $1 -atime +$2)
    echo ${fileList}
}

pruneFiles() {
    local pruneDir=${1}
    local pruneAge=${2}
    fileList=$(grabFiles $pruneDir $pruneAge)
    for file in ${fileList} ; do 
        ${ioNiceExec} rm $file
    done
}

email() {
    local alertEmail=${1}
    local pruneDir=${2}
    local pruneAge=${3}
    local iterations=${4}
    echo "Disk usage for ${pruneDir} from the last ${pruneAge} days is 
    greater than ${maxDisk}%. Deleted ${iterations}d worth of data but
    unable to bring under acceptable thresholds" | mailx -s \
    "ALERT: Nginx Disk Issue for ${HOSTNAME}" ${alertEmail}
}

ioNice() {
    which -s ionice
    if [[ ${?} == 0 ]]; then
        echo "ionice -c 3"
    fi
}

# Main

checkVars

ioNiceExec=$(ioNice)
iterations="0"
diskUsage=$(checkDisk ${pruneDir})

while [[ "${diskUsage}" -gt "${maxDisk}" ]]; do
    if [[ "${minPruneAge}" != "${pruneAge}" ]]; then
        pruneFiles ${pruneDir} ${pruneAge}
        diskUsage=$(checkDisk ${pruneDir})
        let iterations+=1
        let pruneAge-=1
    else
        break 2
    fi
done

if [[ ${diskUsage} -gt ${maxDisk} && ${minPruneAge} == ${pruneAge} ]]; then
    email ${alertEmail} ${pruneDir} ${pruneAge} ${iterations}
fi