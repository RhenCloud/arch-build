import boto3

s3 = boto3.client(
    "s3",
    region_name="cn-north-1",  # 华北-河北区 region id
    endpoint_url="https://s3.cn-north-1.qiniucs.com",  # 华北-河北区 endpoint url
    aws_access_key_id="R7DRO-yN00f7acOnksat430u2G55ApQXCviy_SsP",
    aws_secret_access_key="bX9lr6Xk1bjkHfg8vrqc48uniLP6ZyFCLxOHEEX3",
    config=boto3.session.Config(signature_version="s3v4"),
)
with open("./test.txt", "rb") as f:
    s3.put_object(Bucket="arch-repo", Key="test.txt", Body=f)
# presigned_url = s3.generate_presigned_url(
#     ClientMethod="put_object",
#     Params={"Bucket": "test-bucket", "Key": "test-key"},
#     ExpiresIn=3600,
# )
# print(presigned_url)
