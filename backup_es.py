import boto3
import requests
from requests_aws4auth import AWS4Auth
from pprint import pprint
import datetime
import time
import sys

host = 'https://search-public-es-4534eejzv7iqlh4fobg5sqcylu.us-east-1.es.amazonaws.com/' # include https:// and trailing /
region = 'us-east-1' # e.g. us-west-1
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
# Register repository

path = '_snapshot/my_s3_repository' # the Elasticsearch API endpoint
url = host + path

s3 = boto3.resource('s3')

def delete_bucket():
  bucket = s3.Bucket('backup-es-cloud')
  # suggested by Jordon Philips
  bucket.objects.all().delete()

payload = {
    "type": "s3",
    "indices": "apachelogs",
    "settings": {
      "bucket": "backup-es-cloud",
      "region": "us-east-1",
      "role_arn": "arn:aws:iam::224207291314:role/snapshot-role"
    }
  }
#register the S3 bucket for snapshot
def register_bucket():
  headers = {"Content-Type": "application/json"}
  r = requests.put(url, auth=awsauth, json=payload, headers=headers)
  print(r.status_code)
  print(r.text)


# Take snapshot
def take_snapshot():

  snapshot_name='snapshot'+str(datetime.datetime.now()).replace(' ','_')
  path = '_snapshot/my_s3_repository/'+snapshot_name
  print(snapshot_name)
  url = host + path
  payload ={"wait_for_completion": 'true'}
  r = requests.put(url,json=payload,auth=awsauth)
  print(r)
  print(r.text)



## Restore snapshot (one index)
def restore(index,snapshot):
  path = '_snapshot/my_s3_repository/'+snapshot+'/_restore'
  url = host + path
  
  payload = {"indices": index}
  
  headers = {"Content-Type": "application/json"}
  
  r = requests.post(url, auth=awsauth, json=payload, headers=headers)
  
  print(r.text)


# # Delete index
def delete_index(index):
  url = host + index
  r = requests.delete(url, auth=awsauth) 
  print(r.text)
  

# # Restore snapshots (all indices)
def restore_indices():
  path = '_snapshot/my_s3_repository/snapshot/_restore'
  url = host + path
  r = requests.post(url, auth=awsauth)
  print(r.text)


def remove_older_indices(duration):
  esEndpoint = host
  #1. get the list of all the indices older than the specified duration
  indices = requests.get(host+"_cat/indices", auth=awsauth)
  print("indices:",indices)
  result = indices.text.split('\n')
  del result[-1]
  indicesList=[]
  for line in result:
      indicesList.append(line.split()[2])
  # remove the .kibana4 (or ".kibana" in ES 5.1) index from the list as it is a required/default index in ES
  if ".kibana-4" in indicesList:
      indicesList.remove(".kibana-4")
  elif ".kibana" in indicesList:
      indicesList.remove(".kibana")

  ### Next, get all of the creation times for the various indices...
  creationTimes=[]
  for i in range (0,len(indicesList)):
      cdates = requests.get(esEndpoint+indicesList[i], auth=awsauth)
      cdates2 = cdates.json()
      creationTimes.append(cdates2[indicesList[i]]['settings']['index']['creation_date'])

  print ("\n\nEpoch Timestamps in human readable format are: ")
  print ("IndexName\t\tCreationTime (Epoch)\tCreationTime (Human Readable - UTC)")
  for i in range (0,len(creationTimes)):
      print (indicesList[i]+": \t\t"+creationTimes[i]+"\t\t"+datetime.datetime.fromtimestamp(float(creationTimes[i]) / 1000).strftime('%Y-%m-%d %H:%M:%S'))
  print ("")

  ### Next, determine which indices we should remove. Older than 31 days
  # for testing, tested older than 2 hours ago
  # test offset value (commented out) is the epoch value of 2 hours = 1000ms*60secs*60mins*2hours
  # offset = 7200000
  # offset here is set for 31 days -> 1000ms*60s*60m*24h*31d = 2678400000
  # offset = (1000 * 60 * 60 * 24 * int(sys.argv[2]))

  currentTime = int(time.time() * 1000)
  offset = 900000
  checkTime = currentTime - offset
  removeElements =[]
  # check the element values to see if they are outside the threshold time. Add the index element numbers to an array.
  for i in range (0, len(creationTimes)):
      if checkTime > int(creationTimes[i]):
          removeElements.append(i)

  print ("\nThreshold time (UTC) to check indices against is:")
  print (datetime.datetime.fromtimestamp(checkTime / 1000).strftime('%Y-%m-%d %H:%M:%S'))
  if (len(removeElements) != 0):
      print ("\nThe following indices are candidates for removal:")
      for element in removeElements:
          print (indicesList[element])
          if indicesList[element] =="apachelogs":
              print("taking backups")
              take_snapshot()
              time.sleep(10)
              print("deleting older logs index")
              # delete_index('apachelogs')

  else:
      print ("\nThere are no indices that are older than the threshold time of: " + (datetime.datetime.fromtimestamp(checkTime / 1000).strftime('%Y-%m-%d %H:%M:%S')))
      print ("\nExiting program...")
      print ("-------------------\n\n")
      sys.exit(0)


def lambda_handler(event, context):
    print("in handler")
    print(event)
    # print("taking backups")
    # take_snapshot()
    # time.sleep(10)
    print("finding indexes older than 2 hours")
    remove_older_indices(7200000)
    # print("deleting older logs index")
    # delete_index('apachelogs')


