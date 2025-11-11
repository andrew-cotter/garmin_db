import pandas as pd
import json
import logging
import time
from sqlalchemy import create_engine, exc
import boto3


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# S3 Client
s3_client = boto3.client('s3')
bucket_name = 'aseaotter-garmin'
folder_name = 'activities/'

def get_secret():
    secret_name = "mysql_secret"
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
    except Exception as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

def find_dict_columns(dataframe):
    dict_columns = []
    for column in dataframe.columns:
        # Check if any value in the column is of type dict
        if dataframe[column].apply(lambda x: isinstance(x, dict)).any():
            dict_columns.append(column)
    return dict_columns

def find_list_columns(dataframe):
    list_columns = []
    for column in dataframe.columns:
        # Check if any value in the column is of type list
        if dataframe[column].apply(lambda x: isinstance(x, list)).any():
            list_columns.append(column)
    return list_columns

def main(event, context):
    start_time = time.time()
    print("Lambda function started")

    try:
        # Extract the key (filename) from the event
        object_key = event['Records'][0]['s3']['object']['key']
        print(f"Processing file: {object_key}")

        # Ensure the file is within the 'activities-2' folder
        if not object_key.startswith(folder_name):
            print(f"File is not in the correct folder: {folder_name}")
            return {
                'statusCode': 400,
                'body': f'File is not in the correct folder: {folder_name}'
            }

        # Fetch the JSON file from S3
        print(f"Fetching file from s3{object_key}")
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        print("Fetched")
        json_data = response['Body'].read().decode('utf-8')
        print("Successfully fetched file from S3")

        # Parse the JSON data
        data = json.loads(json_data)
        print("Successfully parsed JSON data")
        
        try:
            activity = pd.DataFrame.from_dict(data, orient="index").transpose()
            print("Successfully converted JSON data to DataFrame")
        except Exception as e:
            print(f"Error converting JSON data to DataFrame: {e}")
            return {
                'statusCode': 500,
                'body': 'Error converting JSON data to DataFrame'
            }
        
        # Drop columns with dicts or lists
        dict_columns = find_dict_columns(activity)
        list_columns = find_list_columns(activity)
        activity = activity.drop(dict_columns + list_columns, axis=1)
        print(f"Dropped columns with dicts or lists: {dict_columns + list_columns}")

        # Connect to MySQL database using pymysql
        secrets = get_secret()
        db_config = {
            'host': secrets["host"],
            'user': secrets["username"],
            'password': secrets["password"],
            'database': secrets["dbname"],
            'port': secrets["port"]
        }

        # Create a connection string for SQLAlchemy using pymysql
        connection_string = (
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        print(connection_string)
        print("Creating SQLAlchemy engine")
        
        # Create an SQLAlchemy engine using pymysql
        engine = create_engine(connection_string)
        
        try:
            # Check the connection
            with engine.connect() as connection:
                print("Successfully connected to the database")
                
                # Define the table name where you want to upload the DataFrame
                table_name = 'activities'
        
                # Upload the DataFrame to the SQL table
                activity.to_sql(name=table_name, con=engine, if_exists='append', index=False)
                print(f"DataFrame uploaded to table '{table_name}'")
        
        except exc.SQLAlchemyError as err:
            print(f"SQLAlchemy Error: {err}")
        
    except Exception as e:
        print(f"General error occurred: {e}")
    
    finally:
        end_time = time.time()
        print(f"Lambda function completed in {end_time - start_time} seconds")