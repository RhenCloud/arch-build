import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import boto3.session

REPO_NAME = os.environ["repo_name"]
ROOT_PATH = os.environ["dest_path"]

# 对象存储配置
S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY_ID", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "")
S3_REGION = os.environ.get("S3_REGION", "")

if ROOT_PATH.startswith("/") and ROOT_PATH != "/":
    ROOT_PATH = ROOT_PATH[1:]

# 分片上传配置
PART_SIZE = 10 * 1024 * 1024  # 5 MB 分片大小
MAX_THREADS = 4  # 最多并发数


def upload_part(s3_client, bucket, key, upload_id, part_number, part_data, lock=None):
    """上传单个分片"""
    try:
        response = s3_client.upload_part(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=part_data,
        )
        return {"PartNumber": part_number, "ETag": response["ETag"]}
    except Exception as e:
        print(f"Failed to upload part {part_number}: {str(e)}")
        raise


def multipart_upload_file(s3_client, file_path, bucket, key):
    """使用分片上传大文件"""
    file_size = file_path.stat().st_size

    # 如果文件小于分片大小，直接上传
    if file_size < PART_SIZE:
        with open(file_path, "rb") as f:
            s3_client.put_object(Bucket=bucket, Key=key, Body=f, ACL="public-read")
        return

    # 大文件分片上传
    print(
        f"Starting multipart upload for {file_path.name} ({file_size / 1024 / 1024:.2f} MB)"
    )

    # 创建分片上传任务
    response = s3_client.create_multipart_upload(Bucket=bucket, Key=key)
    upload_id = response["UploadId"]

    try:
        parts = []
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {}

            with open(file_path, "rb") as f:
                part_number = 1
                while True:
                    part_data = f.read(PART_SIZE)
                    if len(part_data) == 0:
                        break

                    future = executor.submit(
                        upload_part,
                        s3_client,
                        bucket,
                        key,
                        upload_id,
                        part_number,
                        part_data,
                    )
                    futures[future] = part_number
                    part_number += 1

            # 收集上传结果
            for future in as_completed(futures):
                part_info = future.result()
                parts.append(part_info)
                print(f"Uploaded part {part_info['PartNumber']}/{part_number - 1}")

        # 排序分片
        parts.sort(key=lambda x: x["PartNumber"])

        # 完成分片上传
        s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        print(f"Successfully uploaded {key}")

    except Exception:
        # 取消分片上传
        s3_client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
        print(f"Aborted multipart upload for {key}")
        raise


def upload_to_s3():
    """上传所有文件到对象存储"""
    # 初始化 S3 客户端
    s3_client = boto3.client(
        "s3",
        region_name=S3_REGION,
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=boto3.session.Config(signature_version="s3v4"),
    )

    # 遍历当前目录下的所有文件
    current_dir = Path("./")
    files_to_upload = []

    for file_path in current_dir.rglob("*"):
        if file_path.is_file():
            files_to_upload.append(file_path)

    if not files_to_upload:
        print("No files to upload")
        return

    print(f"Uploading {len(files_to_upload)} files to S3...")

    # 使用线程池并行上传多个文件
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {}

        for file_path in files_to_upload:
            relative_path = file_path.relative_to(current_dir)
            # 构建 S3 对象键
            if ROOT_PATH:
                s3_key = f"{ROOT_PATH}/{relative_path}"
            else:
                s3_key = str(relative_path)

            future = executor.submit(upload_file_task, s3_client, file_path, s3_key)
            futures[future] = str(file_path)

        # 等待所有上传任务完成
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Failed to upload {futures[future]}: {str(e)}")
                raise


def upload_file_task(s3_client, file_path, s3_key):
    """单个文件上传任务"""
    try:
        print(f"Uploading {file_path.name} to s3://{S3_BUCKET}/{s3_key}")
        multipart_upload_file(s3_client, file_path, S3_BUCKET, s3_key)
    except Exception as e:
        print(f"Failed to upload {file_path.name}: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        upload_to_s3()
        print("Upload completed successfully")
    except Exception as e:
        print(f"Failed when uploading to object storage: {str(e)}")
        exit(1)
