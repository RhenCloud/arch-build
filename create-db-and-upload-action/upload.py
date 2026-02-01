import os
from pathlib import Path

import boto3

REPO_NAME = os.environ["repo_name"]
ROOT_PATH = os.environ["dest_path"]

# 对象存储配置
S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY_ID", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")

if ROOT_PATH.startswith("/"):
    ROOT_PATH = ROOT_PATH[1:]


def upload_to_s3():
    """上传所有文件到对象存储"""
    # 初始化 S3 客户端
    s3_config = {
        "aws_access_key_id": S3_ACCESS_KEY,
        "aws_secret_access_key": S3_SECRET_KEY,
        "region_name": S3_REGION,
    }

    if S3_ENDPOINT:
        s3_config["endpoint_url"] = S3_ENDPOINT

    s3_client = boto3.client("s3", **s3_config)

    # 遍历当前目录下的所有文件并上传
    current_dir = Path("./")
    files_to_upload = []

    for file_path in current_dir.rglob("*"):
        if file_path.is_file():
            files_to_upload.append(file_path)

    if not files_to_upload:
        print("No files to upload")
        return

    print(f"Uploading {len(files_to_upload)} files to S3...")

    for file_path in files_to_upload:
        relative_path = file_path.relative_to(current_dir)
        # 构建 S3 对象键
        if ROOT_PATH:
            s3_key = f"{ROOT_PATH}/{relative_path}"
        else:
            s3_key = str(relative_path)

        try:
            print(f"Uploading {relative_path} to s3://{S3_BUCKET}/{s3_key}")
            s3_client.upload_file(
                str(file_path), S3_BUCKET, s3_key, ExtraArgs={"ACL": "public-read"}
            )
        except Exception as e:
            print(f"Failed to upload {relative_path}: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        upload_to_s3()
        print("Upload completed successfully")
    except Exception as e:
        print(f"Failed when uploading to object storage: {str(e)}")
        exit(1)
