import boto
import boto.s3.connection
from django.conf import settings

LINODE_ACCESS_KEY = settings.LINODE_ACCESS_KEY
LINODE_SECRET_KEY = settings.LINODE_SECRET_KEY
LINODE_REGION = settings.LINODE_REGION
LINODE_BUCKET_NAME = settings.LINODE_BUCKET_NAME
LINODE_URL = settings.LINODE_URL

conn = boto.connect_s3(
        aws_access_key_id=LINODE_ACCESS_KEY,
        aws_secret_access_key=LINODE_SECRET_KEY,
        host=LINODE_REGION,
        # is_secure=False,               # uncomment if you are not using ssl
        calling_format=boto.s3.connection.OrdinaryCallingFormat(),
        )


def upload_to_linode_object_storage(file_obj, object_key):
    # Connect to Linode Object Storage
    # Get the bucket
    bucket = conn.get_bucket('paulfuther')
    # Create the S3 key
    key = bucket.new_key(object_key)
    # Set the key's contents from the file object
    key.set_contents_from_file(file_obj)
    # Close the connection
    conn.close()


def get_s3_images_for_incident(image_folder, employer):
    bucket_name = LINODE_BUCKET_NAME
    folder_path = f'SITEINCIDENT/{employer}/{image_folder}/'
    images = []
    bucket = conn.get_bucket(bucket_name)
    objects = bucket.list(prefix=folder_path)
    for obj in objects:
        if obj.key.endswith(('jpg', 'jpeg', 'png', 'gif')):
            image_key = obj.key
            image_url = conn.generate_url(expires_in=3600, method='GET',
                                          bucket=bucket_name, key=image_key)
            images.append(image_url)
    return images
