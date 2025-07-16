from pathlib import Path
from typing import List
import boto3

s3_client = boto3.client('s3')

def is_s3_path(path: str) -> bool:
    return path.startswith("s3://")

def list_py_files(path: str) -> List[str]:
    if is_s3_path(path):
        bucket, prefix = parse_s3_path(path)
        return list_py_files_s3(bucket, prefix)
    else:
        p = Path(path)
        return [str(f) for f in p.rglob("*.py") if "DAG" in f.read_text(errors="ignore")]

def read_file(path: str) -> str:
    if is_s3_path(path):
        bucket, key = parse_s3_path(path)
        return read_file_s3(bucket, key)
    else:
        return Path(path).read_text(encoding="utf-8", errors="ignore")

def read_lines(path: str) -> List[str]:
    content = read_file(path)
    return content.splitlines()

def parse_s3_path(s3_path: str) -> (str, str):
    # es. s3://bucket-name/path/to/file.py
    path_parts = s3_path.replace("s3://", "").split("/", 1)
    bucket = path_parts[0]
    prefix = ""
    if len(path_parts) > 1:
        prefix = path_parts[1]
    return bucket, prefix

def list_py_files_s3(bucket: str, prefix: str = "") -> List[str]:
    paginator = s3_client.get_paginator('list_objects_v2')
    py_files = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith(".py"):
                # opzionale: leggi e filtra per contenuto 'DAG'
                obj_body = s3_client.get_object(Bucket=bucket, Key=key)['Body'].read().decode('utf-8', errors='ignore')
                if "DAG" in obj_body:
                    py_files.append(f"s3://{bucket}/{key}")
    return py_files

def read_file_s3(bucket: str, key: str) -> str:
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode('utf-8', errors='ignore')