
from django.conf import settings
from docusign_esign import ApiClient

SCOPES = [
    'signature impersonation'
]


def get_jwt_token(private_key, scopes, auth_server, client_id, impersonated_user_id):
    """Get the jwt token"""
    api_client = ApiClient()
    api_client.set_base_path(auth_server)
    response = api_client.request_jwt_user_token(
        client_id=client_id,
        user_id=impersonated_user_id,
        oauth_host_name=auth_server,
        private_key_bytes=private_key,
        expires_in=4000,
        scopes=scopes
    )
    return response


def create_api_client(base_path, access_token):
    """Create api client and construct API headers"""
    api_client = ApiClient()
    api_client.host = base_path
    api_client.set_default_header(header_name="Authorization",
                                  header_value=f"Bearer {access_token}")

    return api_client


def get_access_token():
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    # Configure your API credentials
    # print(api_client.host)
    clientid = settings.DOCUSIGN_INTEGRATION_KEY
    impersonated_user_id = settings.DOCUSIGN_USER_ID
    in_file = open(settings.DOCUSIGN_PRIVATE_KEY, "rb")
    private_key = in_file.read()
    # print(private_key)
    in_file.close()
    # print(settings.DOCUSIGN_OAUTH_HOST_NAME)
    access_token = api_client.request_jwt_user_token(
        client_id=clientid,
        user_id=impersonated_user_id,
        oauth_host_name=settings.DOCUSIGN_OAUTH_HOST_NAME,
        private_key_bytes=private_key,
        expires_in=3600,
        scopes=SCOPES
            )
    # print(access_token)
    return access_token
