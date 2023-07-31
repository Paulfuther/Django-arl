import os

from docusign_esign import ApiClient

DOCUSIGN_INTEGRATION_KEY = os.environ.get('DOCUSIGN_INTEGRATION_KEY')
DOCUSIGN_USER_ID = os.environ.get('DOCUSIGN_USER_ID')
DOCUSIGN_ACCOUNT_ID = os.environ.get('DOCUSIGN_ACCOUNT_ID')
DOCUSIGN_PRIVATE_KEY = os.environ.get('DOCUSIGN_PRIVATE_KEY')

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
    api_client.host = 'https://ca.docusign.net/restapi/v2.1',
    # Configure your API credentials
    clientid = os.environ.get('DOCUSIGN_INTEGRATION_KEY')
    impersonated_user_id = os.environ.get('DOCUSIGN_USER_ID')
    in_file = open("/Users/paulfuther/Documents/GitHub/Django-arl/arl/private.key", "rb")
    private_key = in_file.read()
    print(private_key)
    in_file.close()
    access_token = api_client.request_jwt_user_token(
        client_id=clientid,
        user_id=impersonated_user_id,
        oauth_host_name="account.docusign.com",
        private_key_bytes=private_key,
        expires_in=3600,
        scopes=SCOPES
            )
    return access_token
