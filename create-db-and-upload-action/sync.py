#!/usr/bin/python3

import glob
import os
import shutil
import tarfile
from contextlib import suppress
from pathlib import Path
from typing import NamedTuple

import boto3
import pyalpm

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

# 初始化 S3 客户端
s3_config = {
    "aws_access_key_id": S3_ACCESS_KEY,
    "aws_secret_access_key": S3_SECRET_KEY,
    "region_name": S3_REGION,
}

if S3_ENDPOINT:
    s3_config["endpoint_url"] = S3_ENDPOINT

s3_client = boto3.client("s3", **s3_config)


class PkgInfo(NamedTuple):
    filename: str
    pkgname: str
    version: str


def get_pkg_infos(file_path: str) -> list["PkgInfo"]:
    """Get packages info from "*.db.tar.gz".

    Args:
        file_path (str): DB file path.

    Returns:
        list["PkgInfo"]: A list contains all packages info.
    """
    with tarfile.open(file_path) as f:
        f.extractall("/tmp/extractdb")

    pkg_infos = []
    pkgs = glob.glob("/tmp/extractdb/*/desc")
    for pkg_desc in pkgs:
        with open(pkg_desc, "r") as f:
            lines = f.readlines()
        lines = [i.strip() for i in lines]
        for index, line in enumerate(lines):
            if "%FILENAME%" in line:
                filename = lines[index + 1]
            if "%NAME%" in line:
                pkgname = lines[index + 1]
            if "%VERSION%" in line:
                version = lines[index + 1]

        pkg_infos.append(PkgInfo(filename, pkgname, version))

    shutil.rmtree("/tmp/extractdb")

    return pkg_infos


def s3_delete(name: str):
    """从 S3 删除文件"""
    try:
        s3_key = f"{ROOT_PATH}/{name}" if ROOT_PATH else name
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        print(f"Deleted s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        raise RuntimeError(f"Failed to delete {name}: {str(e)}")


def s3_download(name: str, dest_path: str = "./"):
    """从 S3 下载文件"""
    try:
        s3_key = f"{ROOT_PATH}/{name}" if ROOT_PATH else name
        dest_file = Path(dest_path) / name
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        s3_client.download_file(S3_BUCKET, s3_key, str(dest_file))
        print(f"Downloaded s3://{S3_BUCKET}/{s3_key} to {dest_file}")
    except Exception as e:
        raise RuntimeError(f"Failed to download {name}: {str(e)}")


def s3_file_exists(name: str) -> bool:
    """检查 S3 中文件是否存在"""
    try:
        s3_key = f"{ROOT_PATH}/{name}" if ROOT_PATH else name
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except:
        return False


def get_old_packages(
    local_packages: list["PkgInfo"], remote_packages: list["PkgInfo"]
) -> list["PkgInfo"]:
    old_packages = []
    for l in local_packages:
        for r in remote_packages:
            if l.pkgname == r.pkgname:
                res = pyalpm.vercmp(l.version, r.version)
                if res > 0:
                    old_packages.append(r)

    return old_packages


def download_local_miss_files(
    local_packages: list["PkgInfo"],
    remote_packages: list["PkgInfo"],
    old_packages: list["PkgInfo"],
):
    local_files = [i.filename for i in local_packages]
    remote_files = [i.filename for i in remote_packages]
    old_files = [i.filename for i in old_packages]
    remote_new_files = [i for i in remote_files if i not in old_files]
    for r in remote_new_files:
        if r not in local_files and ".db" not in r and ".files" not in r:
            with suppress(RuntimeError):
                s3_download(r)


if __name__ == "__main__":
    # 检查远程数据库文件是否存在
    db_filename = f"{REPO_NAME}.db.tar.gz"
    if not s3_file_exists(db_filename):
        print("Remote database file is not exist!")
        print(
            "If you are running this script for the first time, you can ignore this error."
        )
        exit(0)

    local_packages = get_pkg_infos(f"./{REPO_NAME}.db.tar.gz")

    s3_download(db_filename, "/tmp/")
    remote_packages = get_pkg_infos(f"/tmp/{REPO_NAME}.db.tar.gz")

    old_packages = get_old_packages(local_packages, remote_packages)
    for i in old_packages:
        print(f"delete s3://{S3_BUCKET} {i.filename}")
        with suppress(RuntimeError):
            s3_delete(i.filename)
            s3_delete(i.filename + ".sig")

    download_local_miss_files(local_packages, remote_packages, old_packages)
