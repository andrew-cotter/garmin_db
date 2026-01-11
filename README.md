# Garmin DB

A data pipeline for extracting Garmin Connect activity data and loading it into a MySQL database via AWS S3.

## Overview

This repository contains two main components that work together to create an automated data pipeline:

1. **garmin_pull**: Downloads activity data from Garmin Connect and stores it in AWS S3
2. **garmin_push**: Processes activity JSON files from S3 and loads them into a MySQL database

## Architecture

```
Garmin Connect → garmin_pull (Lambda) → S3 → garmin_push (Lambda) → MySQL
```

### Components

- **garmin_pull**: AWS Lambda function that authenticates with Garmin Connect, retrieves activity summaries, and uploads JSON files to S3
- **garmin_push**: AWS Lambda function triggered by S3 events that processes JSON files and inserts activity data into MySQL

## Prerequisites

- AWS Account with:
  - S3 bucket
  - AWS Secrets Manager with:
    - `garmin/connect_login` secret containing Garmin Connect credentials
    - `mysql_secret` secret containing MySQL database credentials
  - Lambda execution role with appropriate permissions
- MySQL database
- Garmin Connect account

## Setup

### 1. AWS Secrets Manager Configuration

Create two secrets in AWS Secrets Manager (region: `us-east-2`):

#### Garmin Connect Secret (`garmin/connect_login`)
```json
{
  "username": "your_garmin_username",
  "pw": "your_garmin_password"
}
```

#### MySQL Secret (`mysql_secret`)
```json
{
  "host": "your_mysql_host",
  "username": "your_mysql_username",
  "password": "your_mysql_password",
  "dbname": "your_database_name",
  "port": 3306
}
```

### 2. S3 Bucket

Create an S3 bucket and configure it to trigger the `garmin_push` Lambda function when new JSON files are added to the `activities/` prefix.

### 3. MySQL Database

Create a table named `activities` in your MySQL database. The schema will be automatically inferred from the activity JSON structure, but ensure the table exists or can be created by SQLAlchemy.

### 4. Installation

#### For garmin_pull:
```bash
cd garmin_pull
pip install -r requirements.txt
```

#### For garmin_push:
```bash
cd garmin_push
pip install -r requirements.txt
```

## Usage

### garmin_pull

The `garmin_pull` module downloads activity data from Garmin Connect and uploads it to S3.

**Main Function:**
```python
from garmin_pull.pull import get_activities

# Download last 90 activities and upload to S3
get_activities("bucket_name", 90, overwrite=False)
```

**Parameters:**
- `bucket_name`: S3 bucket name
- `count`: Number of recent activities to download
- `overwrite`: If `True`, re-uploads existing activities (default: `False`)

**Lambda Handler:**
The `main(event, lambda_context)` function is designed to be used as an AWS Lambda handler. It downloads the last 90 activities by default.

### garmin_push

The `garmin_push` module processes JSON files from S3 and loads them into MySQL.

**Lambda Handler:**
The `main(event, context)` function is designed to be triggered by S3 events. It:
1. Receives an S3 event notification
2. Downloads the JSON file from S3
3. Converts it to a pandas DataFrame
4. Filters out columns containing dictionaries or lists
5. Inserts the data into the MySQL `activities` table

**S3 Event Configuration:**
Configure your S3 bucket to send events to the Lambda function for objects in the `activities/` prefix with `.json` suffix.

## Project Structure

```
garmin_db/
├── garmin_pull/
│   ├── pull.py              # Main pull script
│   └── requirements.txt     # Python dependencies
├── garmin_push/
│   ├── push.py              # Main push script
│   └── requirements.txt     # Python dependencies
├── push_test.ipynb          # Testing notebook
├── requirements.txt         # Root-level dependencies
└── README.md                # This file
```

## Dependencies

### garmin_pull
- `garth`: Garmin Connect API client
- `boto3`: AWS SDK
- `fitfile`: FIT file processing
- `tqdm`: Progress bars

### garmin_push
- `pandas`: Data manipulation
- `sqlalchemy`: Database ORM
- `pymysql`: MySQL driver
- `boto3`: AWS SDK

## Features

- **Incremental Updates**: Skips activities already present in S3 (unless `overwrite=True`)
- **Error Handling**: Comprehensive logging and error handling
- **Rate Limiting**: Includes delays to avoid overwhelming Garmin Connect API
- **Data Cleaning**: Automatically filters out complex nested structures (dicts/lists) before database insertion

## Notes

- The pull function includes a 1-second delay between API calls to be respectful to Garmin's servers
- Activity files are stored in S3 with the prefix `activities/` and named as `activity_{activityId}.json`
- The push function only processes files in the `activities/` folder
- Complex nested data structures (dictionaries and lists) are automatically excluded from database insertion