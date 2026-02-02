#!/bin/bash
set -e

# Set default values for environment variables
local_path="${local_path:-.}"
repo_name="${repo_name:?Error: repo_name is required}"

init_path=$PWD
mkdir upload_packages
find "$local_path" -type f -name "*.tar.zst" -exec cp {} ./upload_packages/ \;

if [ ! -z "$gpg_key" ]; then
    echo "$gpg_key" | gpg --import
fi

cd upload_packages || exit 1

echo "::group::Adding packages to the repo"

repo-add "./${repo_name:?}.db.tar.gz" ./*.tar.zst

echo "::endgroup::"

echo "::group::Removing old packages"

python3 "$init_path"/create-db-and-upload-action/sync.py 

echo "::endgroup::"

rm "./${repo_name:?}.db.tar.gz"
rm "./${repo_name:?}.files.tar.gz"

echo "::group::Signing packages"

if [ ! -z "$gpg_key" ]; then
    for name in ./*.tar.zst
    do
        [ -e "$name" ] || continue
        gpg --detach-sig --yes "$name"
    done
    repo-add --verify --sign "./${repo_name:?}.db.tar.gz" ./*.tar.zst
fi

echo "::endgroup::"

echo "::group::Uploading to object storage"
python3 "$init_path"/create-db-and-upload-action/upload.py 
echo "::endgroup::"
