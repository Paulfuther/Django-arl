import logging
from datetime import date, datetime
from urllib.parse import quote, unquote

import boto
import boto.s3.connection
from botocore.exceptions import NoCredentialsError
from django.conf import settings
from django.http import HttpResponse, HttpResponseServerError
from django.urls import reverse
from django.utils.http import quote

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


def get_s3_images_for_salt_log(image_folder, employer):
    bucket_name = LINODE_BUCKET_NAME
    folder_path = f"SALTLOG/{employer}/{image_folder}/"
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
                    modified_time = datetime.strptime(
                        obj.last_modified, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                except ValueError:
                    logger.warning(
                        f"Unable to parse last_modified string: {obj.last_modified}"
                    )
                    continue
            else:
                modified_time = obj.last_modified.date()

            age_in_days = (
                today - modified_time.date()
            ).days  # Extract date for comparison

            if age_in_days > 7:
                obj.delete()
                deleted_objects += 1

        logger.info(
            f"Old backups removed successfully. Total objects deleted: {deleted_objects}"
        )
        return "Old backups removed successfully"

    except Exception as e:
        logger.error(f"Error occurred during backup cleanup: {e}")
        return f"Error occurred during backup cleanup: {e}"


def list_s3_objects(folder_name):
    try:
        bucket = conn.get_bucket(LINODE_BUCKET_NAME)
        folder_prefix = folder_name
        # Retrieve the objects in the folder
        objects = bucket.list(prefix=folder_prefix)
        # print(objects)
        # Generate links for the files in the folder
        filtered_keys = []
        for obj in objects:
            if obj.key != folder_prefix:  # Skip the folder itself
                file_name = unquote(obj.key[len(folder_prefix):].lstrip('/'))
                encoded_key = quote(obj.key, safe="")  # URL-encode the filename
                # print("key  :", encoded_key)
                link = reverse("download_from_s3", kwargs={"key": encoded_key})
                filtered_keys.append({"name": file_name, "link": link})
                # print(filtered_keys)
                # print("done")
        return filtered_keys

    except NoCredentialsError:
        # Handle exceptions appropriately (e.g., log the error)
        print("Credentials not available")
        return []


def download_from_s3(request, key):
    try:
        # Specify the bucket and key
        bucket_name = LINODE_BUCKET_NAME
        bucket = conn.get_bucket(bucket_name)

        # Fetch the S3 object using get_object
        s3_object = bucket.get_object(key)

        # Generate a pre-signed URL for the S3 object
        url = s3_object.generate_url(3600, query_auth=True, force_http=True)

        # Ensure the filename is URL-encoded
        filename_encoded = quote(key, safe="")

        # Create a response to redirect to the pre-signed URL
        response = HttpResponse(status=302)
        response["Location"] = url

        # Set the Content-Disposition header to suggest a filename
        response["Content-Disposition"] = f'attachment; filename="{filename_encoded}"'

        return response

    except Exception as e:
        # Handle exceptions appropriately (e.g., log the error)
        print(f"Error downloading from S3: {str(e)}")
        return HttpResponse("Error downloading from S3", status=500)

