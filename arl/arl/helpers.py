import logging
from datetime import date, datetime

import boto
import boto.s3.connection
from django.conf import settings

logger = logging.getLogger(__name__)
LINODE_ACCESS_KEY = settings.LINODE_ACCESS_KEY
LINODE_SECRET_KEY = settings.LINODE_SECRET_KEY
LINODE_REGION = settings.LINODE_REGION
LINODE_BUCKET_NAME = settings.LINODE_BUCKET_NAME
LINODE_URL = settings.LINODE_URL

try:
    conn = boto.connect_s3(
        aws_access_key_id=LINODE_ACCESS_KEY,
        aws_secret_access_key=LINODE_SECRET_KEY,
        host=LINODE_REGION,
        # is_secure=False,               # uncomment if you are not using ssl
        calling_format=boto.s3.connection.OrdinaryCallingFormat(),
    )
except Exception as e:
    print("An error occurred while connecting to S3:", e)


def upload_to_linode_object_storage(file_obj, object_key):
    # Connect to Linode Object Storage
    # Get the bucket
    bucket = conn.get_bucket("paulfuther")
    # Create the S3 key
    key = bucket.new_key(object_key)
    # Set the key's contents from the file object
    key.set_contents_from_file(file_obj)
    # Close the connection
    conn.close()


def get_s3_images_for_incident(image_folder, employer):
    bucket_name = LINODE_BUCKET_NAME
    folder_path = f"SITEINCIDENT/{employer}/{image_folder}/"
    images = []
    try:
        bucket = conn.get_bucket(bucket_name)
        objects = bucket.list(prefix=folder_path)
        for obj in objects:
            if obj.key.endswith(("jpg", "jpeg", "png", "gif")):
                image_key = obj.key
                image_url = conn.generate_url(
                    expires_in=3600, method="GET", bucket=bucket_name, key=image_key
                )
                images.append(image_url)
    except Exception as e:
        print("An error occurred:", e)
    return images


def remove_old_backups():
    bucket_name = settings.LINODE_BUCKET_NAME
    folder_path = "POSTGRES/"
    today = date.today()
    try:
        bucket = conn.get_bucket(bucket_name)
        objects = bucket.list(prefix=folder_path)
        deleted_objects = 0

        for obj in objects:
            if isinstance(obj.last_modified, str):
                try:
                    modified_time = datetime.strptime(obj.last_modified, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    logger.warning(f"Unable to parse last_modified string: {obj.last_modified}")
                    continue
            else:
                modified_time = obj.last_modified.date()

            age_in_days = (today - modified_time.date()).days  # Extract date for comparison

            if age_in_days > 7:
                obj.delete()
                deleted_objects += 1

        logger.info(f"Old backups removed successfully. Total objects deleted: {deleted_objects}")
        return "Old backups removed successfully"

    except Exception as e:
        logger.error(f"Error occurred during backup cleanup: {e}")
        return f"Error occurred during backup cleanup: {e}"