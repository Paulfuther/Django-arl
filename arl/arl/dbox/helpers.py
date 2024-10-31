import logging
import os

import dropbox
import requests
from celery.utils.log import get_task_logger
from django.conf import settings
from dropbox.exceptions import ApiError
from dropbox.files import WriteMode

logger = get_task_logger(__name__)


def generate_new_access_token():
    refresh_token = settings.DROP_BOX_REFRESH_TOKEN
    # print(refresh_token)
    if not refresh_token:
        return None
    app_key = settings.DROP_BOX_KEY
    app_secret = settings.DROP_BOX_SECRET
    token_url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret,
    }

    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        response_data = response.json()
        new_access_token = response_data.get("access_token")
        # print("New Access Token: ", new_access_token)
        return new_access_token
    else:
        # Handle error response
        print("Error generating new access token:", response.text)
        return None


def upload_to_dropbox(uploaded_file):
    # Note. This helper file uploads a New Hire File
    # to a folder called NEWHIREFILES
    # New hire quizes have their own helper file.
    # Upload_to_dropbox_quiz
    try:
        new_access_token = generate_new_access_token()
        if new_access_token:
            dbx = dropbox.Dropbox(new_access_token)
            with open(uploaded_file, "rb") as file:
                file_content = file.read()
            # Ensure unique file name in Dropbox by replacing problematic characters
            file_name = os.path.basename(uploaded_file).replace(
                "/", "-"
            )  # Replace '/' with '-'
            file_path = f"/NEWHRFILES/{file_name}"

            # Upload the file content to Dropbox in the NEWHRFILES folder
            dbx.files_upload(file_content, file_path, mode=WriteMode("overwrite"))

            return (
                True,
                print(f"Uploaded file: {file_name} to dropbox."),
                logger.info("{file_name} uploaded to dropbox"),
            )
        else:
            return False, "Refresh token not found in .env file."
    except ApiError as e:
        return False, f"Dropbox API Error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def upload_incident_file_to_dropbox(file_content, file_name):
    try:
        new_access_token = generate_new_access_token()
        if new_access_token:
            dbx = dropbox.Dropbox(new_access_token)
            # Upload the file content to Dropbox
            dbx.files_upload(
                file_content, f"/SITEINCIDENTS/{file_name}", mode=WriteMode("overwrite")
            )
            return True, f"Uploaded file: {file_name} to Dropbox."
        else:
            return False, "Refresh token not found in .env file."
    except dropbox.exceptions.ApiError as e:
        logging.error(f"Dropbox API Error: {str(e)}")
        return False, f"Dropbox API Error: {str(e)}"
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False, f"Error: {str(e)}"


def upload_major_incident_file_to_dropbox(file_content, file_name):
    try:
        new_access_token = generate_new_access_token()
        if new_access_token:
            dbx = dropbox.Dropbox(new_access_token)
            # Upload the file content to Dropbox
            dbx.files_upload(
                file_content, f"/MAJORSITEINCIDENTS/{file_name}",
                mode=WriteMode("overwrite")
            )
            return True, f"Uploaded file: {file_name} to Dropbox."
        else:
            return False, "Refresh token not found in .env file."
    except dropbox.exceptions.ApiError as e:
        logging.error(f"Dropbox API Error: {str(e)}")
        return False, f"Dropbox API Error: {str(e)}"
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False, f"Error: {str(e)}"


def upload_to_dropbox_quiz(uploaded_file):
    # This uploads a completed new hire quiz
    # to dropbox in the folder NEWHIREQUIZ
    
    try:
        new_access_token = generate_new_access_token()
        if new_access_token:
            dbx = dropbox.Dropbox(new_access_token)
            with open(uploaded_file, "rb") as file:
                file_content = file.read()
            # Ensure unique file name in Dropbox by replacing problematic characters
            file_name = os.path.basename(uploaded_file).replace(
                "/", "-"
            )  # Replace '/' with '-'
            file_path = f"/NEWHIREQUIZ/{file_name}"

            # Upload the file content to Dropbox in the NEWHRFILES folder
            dbx.files_upload(file_content, file_path, mode=WriteMode("overwrite"))

            return (
                True,
                print(f"Uploaded file: {file_name} to dropbox."),
                logger.info("{file_name} uploaded to dropbox"),
            )
        else:
            return False, "Refresh token not found in .env file."
    except ApiError as e:
        return False, f"Dropbox API Error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"
    


def upload_any_file_to_dropbox(file_content, file_name, object_key=None):
    try:
        new_access_token = generate_new_access_token()
        if new_access_token:
            dbx = dropbox.Dropbox(new_access_token)
            # Use object_key for path if provided, otherwise default to /UPLOADERRORS
            dropbox_path = f"/{object_key}" if object_key else f"/UPLOADERRORS/{file_name}"
            # Upload the file content to Dropbox
            dbx.files_upload(
                file_content, dropbox_path, mode=dropbox.files.WriteMode("overwrite")
            )
            return True, f"Uploaded file: {file_name} to Dropbox at {dropbox_path}."
        else:
            return False, "Refresh token not found in .env file."
    except dropbox.exceptions.ApiError as e:
        logging.error(f"Dropbox API Error: {str(e)}")
        return False, f"Dropbox API Error: {str(e)}"
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False, f"Error: {str(e)}"