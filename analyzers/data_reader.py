from pathlib import Path  ## Used for handling local filesystem paths
from typing import List    ## For type hinting lists
import boto3              ## AWS SDK to interact with S3

s3_client = boto3.client('s3')  ## Initialize S3 client

def is_s3_path(path: str) -> bool:
    ## Check if the path is an S3 path
    return path.startswith("s3://")

def list_py_files(path: str) -> List[str]:
    ## Return a list of .py files containing "DAG" in their content
    if is_s3_path(path):
        bucket, prefix = parse_s3_path(path)
        return list_py_files_s3(bucket, prefix)
    else:
        p = Path(path)
        ## Recursively search for .py files and filter by content
        return [str(f) for f in p.rglob("*.py") if "DAG" in f.read_text(errors="ignore")]

def read_file(path: str) -> str:
    ## Read the content of a file (from local or S3)
    if is_s3_path(path):
        bucket, key = parse_s3_path(path)
        return read_file_s3(bucket, key)
    else:
        return Path(path).read_text(encoding="utf-8", errors="ignore")

def read_lines(path: str) -> List[str]:
    ## Read a file and return its content as a list of lines
    content = read_file(path)
    return content.splitlines()

def parse_s3_path(s3_path: str) -> (str, str):
    ## Parse an S3 URI into bucket and key
    # Example input: s3://bucket-name/path/to/file.py
    path_parts = s3_path.replace("s3://", "").split("/", 1)
    bucket = path_parts[0]
    prefix = ""
    if len(path_parts) > 1:
        prefix = path_parts[1]
    return bucket, prefix

def list_py_files_s3(bucket: str, prefix: str = "") -> List[str]:
    ## List .py files in S3 that contain "DAG" in their content
    paginator = s3_client.get_paginator('list_objects_v2')
    py_files = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith(".py"):
                ## Read content to check if it includes "DAG"
                obj_body = s3_client.get_object(Bucket=bucket, Key=key)['Body'].read().decode('utf-8', errors='ignore')
                if "DAG" in obj_body:
                    py_files.append(f"s3://{bucket}/{key}")
    return py_files

def read_file_s3(bucket: str, key: str) -> str:
    ## Read and return the content of a file stored in S3
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode('utf-8', errors='ignore')
