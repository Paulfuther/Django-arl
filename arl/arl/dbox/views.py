# your_app_name/views.py

import os

import dropbox
import requests
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import ApiError
from dropbox.files import FolderMetadata, ListFolderResult

app_key = settings.DROP_BOX_KEY
app_secret = settings.DROP_BOX_SECRET


def dropbox_auth(request):
    # Replace with your actual app key and secret
    auth_flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type='offline')

    authorize_url = auth_flow.start()
    # Print the URL or redirect the user to this URL
    print("1. Go to: " + authorize_url)
    print("2. Click \"Allow\" (you might have to log in first).")
    print("3. After authorization, you will be redirected to the redirect URL.")
    return HttpResponse("Authorization URL printed to console.")


def use_dropbox(request):
    # Replace with your actual app key and secret
    # Use the authorization code to obtain tokens
    authorization_code = 'ZsbiIpbNLlkAAAAAAAAAZrrB7pjzTezdkK4q_hVC8xc'  # Replace with the actual
    # authorization code
    auth_flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type='offline')
    oauth_result = auth_flow.finish(authorization_code)
    # Access token allows access to the user's Dropbox account
    access_token = oauth_result.access_token

    # Refresh token can be used to obtain a new access token when needed
    refresh_token = oauth_result.refresh_token
    print(access_token, refresh_token)

    # Now you can use the access_token and refresh_token for API calls and token management
    dbx = dropbox.Dropbox(oauth2_access_token=access_token)
    try:
        account_info = dbx.users_get_current_account()
        return HttpResponse(f"Successfully authenticated as {account_info.name.display_name}.")
    except dropbox.exceptions.AuthError as e:
        return HttpResponse("Authentication failed: " + str(e))


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
        "client_secret": app_secret
    }

    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        response_data = response.json()
        new_access_token = response_data.get('access_token')
        print('New Access Token: ', new_access_token)
        return new_access_token
    else:
        # Handle error response
        print("Error generating new access token:", response.text)
        return None


def list_folders(request):
    new_access_token = generate_new_access_token()
    if new_access_token:
        # Use the new access token to create the Dropbox client
        dbx = dropbox.Dropbox(oauth2_access_token=new_access_token)
        try:
            folder_list = dbx.files_list_folder(path="")
            folders = [entry for entry in folder_list.entries if isinstance(entry, FolderMetadata)]
            return render(request, 'dbox/list_folders.html', {'folder_list':
                                                              folder_list, 'folders': folders})
        except dropbox.exceptions.AuthError as e:
            return HttpResponse("API request failed. Authentication error: " + str(e))
        except dropbox.exceptions.ApiError as e:
            return HttpResponse("API request failed. API error: " + str(e))
        except Exception as e:
            return HttpResponse("API request failed. Error: " + str(e))
    else:
        return HttpResponse("Refresh token not found in .env file.", status=500)


def list_files(request, folder_name):
    new_access_token = generate_new_access_token()
    if new_access_token:
        dbx = dropbox.Dropbox(oauth2_access_token=new_access_token)
        try:
            # Make API request to list files within the specified folder
            folder_path = f"/{folder_name}"
            file_list = dbx.files_list_folder(path=folder_path)
            if isinstance(file_list, ListFolderResult):
                file_names = [
                    entry.name for entry in file_list.entries if isinstance(entry,
                                                                            dropbox.files.
                                                                            FileMetadata)
                ]
                return render(request, 'list_files.html', {'folder_name': folder_name,
                                                           'file_names': file_names})
            else:
                return HttpResponse("API request failed. Invalid response format.")
        except dropbox.exceptions.AuthError as e:
            return HttpResponse("API request failed. Authentication error: " + str(e))
        except dropbox.exceptions.ApiError as e:
            return HttpResponse("API request failed. API error: " + str(e))
        except Exception as e:
            return HttpResponse("API request failed. Error: " + str(e))
    else:
        return HttpResponse("Refresh token not found in .env file.", status=500)


def download_file(request):
    file_path = request.GET.get('path', '')

    if not file_path:
        return HttpResponse("File path is missing.", status=400)
    access_token = generate_new_access_token()
    try:
        dbx = dropbox.Dropbox(access_token)

        metadata, response = dbx.files_download(file_path)
        response = HttpResponse(content=response.content)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    except ApiError as e:
        return HttpResponse(f"Failed to download file: {str(e)}", status=500)


def view_folder(request):
    new_access_token = generate_new_access_token()
    if new_access_token:
        # Use the new access token to create the Dropbox client
        dbx = dropbox.Dropbox(oauth2_access_token=new_access_token)

        try:
            # Make API request to list the root folder
            folder_list = dbx.files_list_folder(path="")
            if isinstance(folder_list, ListFolderResult):
                folders = [
                    entry for entry in folder_list.entries if isinstance(entry,
                                                                         dropbox.
                                                                         files.FolderMetadata)
                ]
                return render(request, 'list_folders.html', {'folders': folders})
            else:
                return HttpResponse("API request failed. Invalid response format.")
        except dropbox.exceptions.AuthError as e:
            return HttpResponse("API request failed. Authentication error: " + str(e))
        except dropbox.exceptions.ApiError as e:
            return HttpResponse("API request failed. API error: " + str(e))
        except Exception as e:
            return HttpResponse("API request failed. Error: " + str(e))
    else:
        return HttpResponse("Refresh token not found in .env file.", status=500)


def list_folder_contents(request, path=''):
    new_access_token = generate_new_access_token()
    if new_access_token:
        dbx = dropbox.Dropbox(oauth2_access_token=new_access_token)
        try:
            folder_list = dbx.files_list_folder(path)
            if isinstance(folder_list, dropbox.files.ListFolderResult):
                files = [
                    entry for entry in folder_list.entries
                    if isinstance(entry, dropbox.files.FileMetadata)
                ]
                return render(request, 'dbox/list_folder_contents.html', {'files': files,
                                                                          'folder_path': path})
            else:
                return HttpResponse("API request failed. Invalid response format.")
        except dropbox.exceptions.AuthError as e:
            return HttpResponse("API request failed. Authentication error: " + str(e))
        except dropbox.exceptions.ApiError as e:
            return HttpResponse("API request failed. API error: " + str(e))
        except Exception as e:
            return HttpResponse("API request failed. Error: " + str(e))
    else:
        return HttpResponse("Refresh token not found in .env file.", status=500)
