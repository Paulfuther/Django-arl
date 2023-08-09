import requests
from django.conf import settings


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
