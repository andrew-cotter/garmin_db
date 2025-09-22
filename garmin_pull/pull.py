import garth
from garth.exc import GarthHTTPError, GarthException
import logging
import tempfile
import time
from tqdm import tqdm
import os
import json
import fitfile.conversions as conversions
import zipfile
import requests
import boto3
from botocore.exceptions import ClientError

def get_secret():
    secret_name = "garmin/connect_login"
    region_name = "us-east-2"
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except boto3.ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
garmin_connect_activity_search_url = "/activitylist-service/activities/search/activities"
garmin_connect_download_service_url = "/download-service/files"
secret = get_secret()
garth.login(secret["username"], secret["pw"])
garth.configure(domain="garmin.com")
s3_client = boto3.client("s3", region_name="us-east-2")

def convert_to_json(obj):
    return obj.__str__()

def upload_json_to_s3(bucket_name, key, json_data):
    """Upload JSON formatted data to an S3 bucket."""
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(json_data, default=convert_to_json),
            ContentType='application/json'
        )
        logger.debug("Uploaded JSON to S3: %s", key)
    except Exception as e:
        logger.error("Failed to upload JSON to S3: %s", e)

def unzip_and_upload_to_s3(temp_dir, bucket_name, s3_prefix):
    """Unzip files and upload to S3."""
    logger.info("Unzipping files from %s and uploading to S3 with prefix %s", temp_dir, s3_prefix)
    for filename in os.listdir(temp_dir):
        if filename.endswith('.zip'):
            full_pathname = os.path.join(temp_dir, filename)
            with zipfile.ZipFile(full_pathname, 'r') as files_zip:
                for file_info in files_zip.infolist():
                    file_data = files_zip.read(file_info.filename)
                    s3_key = f'{s3_prefix}/{file_info.filename}'
                    try:
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=s3_key,
                            Body=file_data,
                            ContentType='application/octet-stream'
                        )
                        logger.debug("Uploaded %s to S3: %s", file_info.filename, s3_key)
                    except Exception as e:
                        logger.error("Failed to upload %s to S3: %s", file_info.filename, e)

def upload_binary_to_s3(bucket_name, key, url):
    """Upload binary data to an S3 bucket."""
    try:
        response = garth.connectapi(url)  # Fetch binary data
        s3_client.upload_fileobj(response, bucket_name, key)
        logger.debug("Uploaded binary file to S3: %s", key)
    except Exception as e:
        logger.error("Failed to upload binary file to S3: %s", e)

def get_activity_summaries(start, count):
    logger.info("get_activity_summaries")
    params = {
        'start': str(start),
        'limit': str(count)
    }
    try:
        return garth.connectapi(garmin_connect_activity_search_url, params=params)
    except GarthHTTPError as e:
        logger.error("Exception getting activity summary: %s", e)
        return []

def save_activity_file(temp_dir, activity_id_str):
    # This function is no longer needed if uploading directly to S3
    pass

def s3_file_exists(bucket_name, key):
    """Check if a file exists in an S3 bucket."""
    try:
        s3_client.head_object(Bucket=bucket_name, Key=key)
        print(f"skipping {key}")
        return True
    except s3_client.exceptions.ClientError:
        return False

def get_activities(bucket_name, count, overwrite=False):
    """Download activity files from Garmin Connect and upload to S3."""
    temp_dir = tempfile.mkdtemp()
    logger.info("Getting activities: count %d, temp %s", count, temp_dir)
    activities = get_activity_summaries(0, count)
    s3_prefix = 'activities'  # Define a prefix for S3

    for activity in tqdm(activities or [], unit='activities'):
        activity_id_str = str(activity['activityId'])
        activity_name_str = conversions.printable(activity['activityName'])
        logger.info("Processing: %s (%s)", activity_name_str, activity_id_str)
        json_key = f'{s3_prefix}/activity_{activity_id_str}.json'
        if overwrite or not s3_file_exists(bucket_name, json_key):
            logger.info("Uploading activity JSON to S3: %s", json_key)
            upload_json_to_s3(bucket_name, json_key, activity)
            time.sleep(1)  # Pause for a second between every page access
        else:
            logger.info("Skipping upload of %s, already present in S3", activity_id_str)
    unzip_and_upload_to_s3(temp_dir, bucket_name, s3_prefix)
    

def main(event, lambda_context):
    get_activities("aseaotter-garmin", 90)