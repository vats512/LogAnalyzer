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

path = 'apachelogs/_search' # the Elasticsearch API endpoint
url = host + path
arn = 'arn:aws:sns:us-east-1:224207291314:ProjectAlertNotifications'

threshold_403 = 10
threshold_404 = 10
threshold_500 = 10

def lambda_handler(event, context):
    # remove_older_indices(7200000)
    url = host + path
    payload ={
        "query": {
          "bool": {
              "filter": {
                "range": { 
                  "datetime": { 
                    "gt" : "now-30m",
                    "lt": "now"
                    
                  }
                } 
              }
          }
        }
    }
    headers = {"Content-Type": "application/json"}
    r = requests.get(url, auth=awsauth, json=payload, headers=headers)
    total = r.json()['hits']['total']
    
    payload ={
        "query": {
          "bool": {
              "must":{ 
                "match": { "response": "403" }
              },
              "filter": {
                "range": { 
                  "datetime": { 
                    "gt" : "now-30m",
                    "lt": "now"
                    
                  }
                } 
              }
          }
        }
    }
    headers = {"Content-Type": "application/json"}
    r = requests.get(url, auth=awsauth, json=payload, headers=headers)
    error_403 = r.json()['hits']['total']
    
    payload ={
        "query": {
            "bool": {
                "must":{ 
                    "match": { "response": "404" }
                },
                "filter": {
                    "range": { 
                        "datetime": { 
                            "gt" : "now-30m",
                            "lt": "now"  
                        }
                    } 
                }
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    r = requests.get(url, auth=awsauth, json=payload, headers=headers)
    error_404 = r.json()['hits']['total']
    
    payload ={
        "query": {
            "bool": {
              "must":{ 
                "range" : 
                {
                  "response" : {
                      "gte": "500",
                      "lt" : "600"
                  }
                }
              },
                "filter": {
                    "range": { 
                      "datetime": { 
                        "gt" : "now-30m",
                        "lt": "now"
                        
                        }
                    } 
                }
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    r = requests.get(url, auth=awsauth, json=payload, headers=headers)
    error_500 = r.json()['hits']['total']
    
    if (total != 0):
        error_per_403 = (error_403 / total) * 100
        error_per_404 = (error_404 / total) * 100
        error_per_500 = (error_500 / total) * 100
    else:
        error_per_403,error_per_500,error_per_404 = 0,0,0
    message = []
    
    if(error_per_500 > threshold_500):
        message.append("[ERROR - 500]\nThe Number of INTERNAL SERVER ERROR has exceeded the threshold specified with about {0:.2f}% requests.\n\n".format(round(error_per_500,2)))
    else:
        message.append("[STATUS - 500]\nThe Number of INTERNAL SERVER ERROR is under monitoring. No Unusual behaviour is found at this Moment.\n\n")
    if(error_per_404 > threshold_404):
        message.append("[ERROR - 404]\nThe Number of PAGE NOT FOUND Responses has exceeded the threshold specified with about {0:.2f}% requests.\n\n".format(round(error_per_404,2)))
    else:
        message.append("[STATUS - 404]\nThe Number of PAGE NOT FOUND Responses is under monitoring. No Unusual behaviour is found at this Moment.\n\n")
    if(error_per_403 > threshold_403):
        message.append("[ERROR - 403]\nThe Number of MISSING AUTHENTICATION TOKEN Requests has exceeded the threshold specified with about {0:.2f}% requests.\n\n".format(round(error_per_403,2)))
    else:
        message.append("[STATUS - 500]\nThe Number of MISSING AUTHENTICATION TOKEN Requests is under monitoring. No Unusual behaviour is found at this Moment.\n\n")
    print(error_per_403, error_per_404, error_per_500)
    alert_message = ''.join(message)
    
    client = boto3.client('sns')
    response = client.publish(
        TargetArn=arn,
        Message=alert_message,
        Subject='[ALERT] - Server Monitoring ALERT',
        MessageStructure='text'
    )
    
    

