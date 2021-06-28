#!/usr/bin/env python
"""Add Physical Linux Servers to File-based Protection Job Using Python"""

### usage: ./protectLinux.py -v mycluster \
#                            -u myuser \
#                            -d mydomain.net \
#                            -j 'My Backup Job' \
#                            -s myserver1.mydomain.net \
#                            -s myserver2.mydomain.net \
#                            -l serverlist.txt \
#                            -i /var \
#                            -i /home \
#                            -e /var/log \
#                            -e /home/oracle \
#                            -e *.dbf \
#                            -f excludes.txt

### import pyhesity wrapper module
from pyhesity import *

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, required=True)
parser.add_argument('-u', '--username', type=str, required=True)
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-k', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-s', '--servername', action='append', type=str)
parser.add_argument('-l', '--serverlist', type=str)
parser.add_argument('-j', '--jobname', type=str, required=True)
parser.add_argument('-a', '--alllocaldrives', action='store_true')
parser.add_argument('-mf', '--metadatafile', type=str, default=None)
parser.add_argument('-i', '--include', action='append', type=str)
parser.add_argument('-n', '--includefile', type=str)
parser.add_argument('-e', '--exclude', action='append', type=str)
parser.add_argument('-x', '--excludefile', type=str)
parser.add_argument('-m', '--skipnestedmountpoints', action='store_true')
parser.add_argument('-t', '--skipnestedmountpointtypes', action='append', type=str)
parser.add_argument('-sd', '--storagedomain', type=str, default='DefaultStorageDomain')
parser.add_argument('-p', '--policyname', type=str, default=None)
parser.add_argument('-tz', '--timezone', type=str, default='US/Eastern')
parser.add_argument('-st', '--starttime', type=str, default='21:00')
parser.add_argument('-is', '--incrementalsla', type=int, default=60)    # incremental SLA minutes
parser.add_argument('-fs', '--fullsla', type=int, default=120)          # full SLA minutes
parser.add_argument('-ei', '--enableindexing', action='store_true')     # enable indexing

args = parser.parse_args()

vip = args.vip                        # cluster name/ip
username = args.username              # username to connect to cluster
domain = args.domain                  # domain of username (e.g. local, or AD domain)
password = args.password              # password or API key
useApiKey = args.useApiKey            # use API key for authentication
servernames = args.servername         # name of server to protect
serverlist = args.serverlist          # file with server names
jobname = args.jobname                # name of protection job to add server to
alllocaldrives = args.alllocaldrives  # protect all local drives
metadatafile = args.metadatafile      # metadata file path
includes = args.include               # include path
includefile = args.includefile        # file with include paths
excludes = args.exclude               # exclude path
excludefile = args.excludefile        # file with exclude paths
skipmountpoints = args.skipnestedmountpoints                # skip nested mount points (6.3 and below)
skipnestedmountpointtypes = args.skipnestedmountpointtypes  # skip nester mount point types (6.4 and above)
storagedomain = args.storagedomain    # storage domain for new job
policyname = args.policyname          # policy name for new job
starttime = args.starttime            # start time for new job
timezone = args.timezone              # time zone for new job
incrementalsla = args.incrementalsla  # incremental SLA for new job
fullsla = args.fullsla                # full SLA for new job
enableindexing = args.enableindexing  # enable indexing on new job

# read server file
if servernames is None:
    servernames = []
if serverlist is not None:
    f = open(serverlist, 'r')
    servernames += [s.strip() for s in f.readlines() if s.strip() != '']
    f.close()

if len(servernames) == 0:
    print('no servers specified')
    exit()

# read include file

if alllocaldrives is True:
    includes = ['$ALL_LOCAL_DRIVES']
else:
    if includes is None:
        includes = []
    if includefile is not None:
        f = open(includefile, 'r')
        includes += [e.strip() for e in f.readlines() if e.strip() != '']
        f.close()
    if len(includes) == 0:
        includes += '/'

# read exclude file
if excludes is None:
    excludes = []
if excludefile is not None:
    f = open(excludefile, 'r')
    excludes += [e.strip() for e in f.readlines() if e.strip() != '']
    f.close()

# authenticate to Cohesity
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey)

# get job info
newJob = False
protectionGroups = api('get', 'data-protect/protection-groups?isDeleted=false&isActive=true', v=2)
jobs = protectionGroups['protectionGroups']
job = [job for job in jobs if job['name'].lower() == jobname.lower()]

if not job or len(job) < 1:
    newJob = True
    print("Job '%s' not found. Creating new job" % jobname)

    # find protectionPolicy
    if policyname is None:
        print('Policy name required for new job')
        exit(1)
    policy = [p for p in api('get', 'protectionPolicies') if p['name'].lower() == policyname.lower()]
    if len(policy) < 1:
        print("Policy '%s' not found!" % policyname)
        exit(1)
    policyid = policy[0]['id']

    # find storage domain
    sd = [sd for sd in api('get', 'viewBoxes') if sd['name'].lower() == storagedomain.lower()]
    if len(sd) < 1:
        print("Storage domain %s not found!" % storagedomain)
        exit(1)
    sdid = sd[0]['id']

    # parse starttime
    try:
        (hour, minute) = starttime.split(':')
        hour = int(hour)
        minute = int(minute)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            print('starttime is invalid!')
            exit(1)
    except Exception:
        print('starttime is invalid!')
        exit(1)

    job = {
        "name": jobname,
        "policyId": policyid,
        "priority": "kMedium",
        "storageDomainId": sdid,
        "description": "",
        "startTime": {
            "hour": int(hour),
            "minute": int(minute),
            "timeZone": timezone
        },
        "alertPolicy": {
            "backupRunStatus": [
                "kFailure"
            ],
            "alertTargets": []
        },
        "sla": [
            {
                "backupRunType": "kIncremental",
                "slaMinutes": int(incrementalsla)
            },
            {
                "backupRunType": "kFull",
                "slaMinutes": int(fullsla)
            }
        ],
        "qosPolicy": "kBackupHDD",
        "abortInBlackouts": False,
        "isActive": True,
        "isPaused": False,
        "environment": "kPhysical",
        "permissions": [],
        "physicalParams": {
            "protectionType": "kFile",
            "fileProtectionTypeParams": {
                "objects": [],
                "indexingPolicy": {
                    "enableIndexing": enableindexing,
                    "includePaths": [
                        "/"
                    ],
                    "excludePaths": [
                        "/$Recycle.Bin",
                        "/Windows",
                        "/Program Files",
                        "/Program Files (x86)",
                        "/ProgramData",
                        "/System Volume Information",
                        "/Users/*/AppData",
                        "/Recovery",
                        "/var",
                        "/usr",
                        "/sys",
                        "/proc",
                        "/lib",
                        "/grub",
                        "/grub2",
                        "/opt/splunk",
                        "/splunk"
                    ]
                },
                "performSourceSideDeduplication": False,
                "dedupExclusionSourceIds": None,
                "globalExcludePaths": None
            }
        }
    }

else:
    job = job[0]
    if 'physicalParams' not in job or job['physicalParams']['protectionType'] != 'kFile':
        print("Job '%s' is not a file-based physical protection job" % jobname)
        exit(1)

# get registered physical servers
physicalServersRoot = api('get', 'protectionSources/rootNodes?allUnderHierarchy=false&environments=kPhysicalFiles&environments=kPhysical&environments=kPhysical')
physicalServersRootId = physicalServersRoot[0]['protectionSource']['id']
physicalServers = api('get', 'protectionSources?allUnderHierarchy=false&id=%s&includeEntityPermissionInfo=true' % physicalServersRootId)[0]['nodes']

for servername in servernames:
    # find server
    physicalServer = [s for s in physicalServers if s['protectionSource']['name'].lower() == servername.lower() and s['protectionSource']['physicalProtectionSource']['hostType'] != 'kWindows']
    if not physicalServer:
        print("******** %s is not a registered Linux/AIX/Solaris server ********" % servername)
    else:
        physicalServer = physicalServer[0]

        # get sourceSpecialParameters
        existingobject = [o for o in job['physicalParams']['fileProtectionTypeParams']['objects'] if o['id'] == physicalServer['protectionSource']['id']]
        if len(existingobject) > 0:
            thisobject = existingobject[0]
            thisobject['filePaths'] = []
            print('  updating %s in job %s...' % (servername, jobname))
            newObject = False
        else:
            thisobject = {
                "id": physicalServer['protectionSource']['id'],
                "name": physicalServer['protectionSource']['name'],
                "filePaths": [],
                "usesPathLevelSkipNestedVolumeSetting": False,
                "nestedVolumeTypesToSkip": [
                    "autofs"
                ],
                "followNasSymlinkTarget": False
            }
            print('  adding %s to job %s...' % (servername, jobname))
            newObject = True

        if metadatafile is not None:
            thisobject['metadataFilePath'] = metadatafile
        else:
            thisobject['metadataFilePath'] = None
            for include in includes:
                filePath = {
                    "includedPath": include,
                    "excludedPaths": [],
                    "skipNestedVolumes": skipmountpoints
                }

            thisobject['filePaths'].append(filePath)

            for exclude in excludes:
                thisParent = ''
                for include in includes:
                    if include in exclude and '/' in exclude:
                        if len(include) > len(thisParent):
                            thisParent = include
                if alllocaldrives is True:
                    thisParent = '$ALL_LOCAL_DRIVES'
                for filePath in thisobject['filePaths']:
                    if thisParent == '' or filePath['includedPath'] == thisParent:
                        filePath['excludedPaths'].append(exclude)

        # add mount point type exclusions
        if skipnestedmountpointtypes is not None and len(skipnestedmountpointtypes) > 0:
            for mountpointtype in skipnestedmountpointtypes:
                if mountpointtype not in thisobject['nestedVolumeTypesToSkip']:
                    thisobject['nestedVolumeTypesToSkip'].append(mountpointtype)

        # include new parameter
        if newObject is True:
            job['physicalParams']['fileProtectionTypeParams']['objects'].append(thisobject)

# update job
if newJob is True:
    result = api('post', 'data-protect/protection-groups', job, v=2)
else:
    result = api('put', 'data-protect/protection-groups/%s' % job['id'], job, v=2)
