# money/utils/s3_utils.py
import boto3
from django.conf import settings

def get_s3_client():
    """
    Initializes and returns an S3 client.
    """
    session = boto3.session.Session()
    s3_client = session.client(
        service_name='s3',
        endpoint_url=settings.YANDEX_ENDPOINT,
        aws_access_key_id=settings.YANDEX_ACCESS_KEY,
        aws_secret_access_key=settings.YANDEX_SECRET_KEY,
    )
    return s3_client