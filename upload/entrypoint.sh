#!/bin/bash
set -e

init_path=$PWD
mkdir upload_packages
find $local_path -type f -name "*.tar.zst" -exec cp {} ./upload_packages/ \;
find $local_path -type f -name "*.tar.gz" -exec cp {} ./upload_packages/ \;
find $local_path -type f -name "*.sig" -exec cp {} ./upload_packages/ \;
find $local_path -type f -name "*.db" -exec cp {} ./upload_packages/ \;
find $local_path -type f -name "*.files" -exec cp {} ./upload_packages/ \;

cd upload_packages

echo "::group::Uploading to object storage"

# 使用 Python boto3 上传到 S3
python3 << 'EOF'
import os
import boto3
from pathlib import Path

S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY_ID", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
dest_path = os.environ.get("dest_path", "")

if dest_path.startswith("/"):
    dest_path = dest_path[1:]

# 初始化 S3 客户端
s3_config = {
    'aws_access_key_id': S3_ACCESS_KEY,
    'aws_secret_access_key': S3_SECRET_KEY,
    'region_name': S3_REGION
}

if S3_ENDPOINT:
    s3_config['endpoint_url'] = S3_ENDPOINT

s3_client = boto3.client('s3', **s3_config)

# 上传当前目录下的所有文件
current_dir = Path("./")
for file_path in current_dir.iterdir():
    if file_path.is_file():
        if dest_path:
            s3_key = f"{dest_path}/{file_path.name}"
        else:
            s3_key = file_path.name
        
        print(f"Uploading {file_path.name} to s3://{S3_BUCKET}/{s3_key}")
        s3_client.upload_file(
            str(file_path),
            S3_BUCKET,
            s3_key,
            ExtraArgs={'ACL': 'public-read'}
        )

print("Upload completed successfully")
EOF

echo "::endgroup::"
