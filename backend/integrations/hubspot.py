# hubspot.py

import base64
import json
import os
import secrets
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
import httpx
import requests

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, delete_key_redis, get_value_redis

load_dotenv()

CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'
TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'
SCOPE = 'oauth crm.objects.contacts.read crm.objects.companies.read crm.objects.deals.read'


def _get_hubspot_item_name(properties, item_type='Contact'):
    if item_type == 'Contact':
        first = properties.get('firstname', '')
        last = properties.get('lastname', '')
        full_name = f'{first} {last}'.strip()
        if full_name:
            return full_name
        if properties.get('email'):
            return properties['email']

    for key in ['dealname', 'name', 'company', 'email', 'hs_object_id']:
        value = properties.get(key)
        if value:
            return value
    return 'HubSpot Object'


def create_integration_item_metadata_object(response_json, item_type='Contact'):
    properties = response_json.get('properties', {})
    item_name = _get_hubspot_item_name(properties, item_type)
    return IntegrationItem(
        id=response_json.get('id'),
        type=item_type,
        name=item_name,
        parent_id=None,
        parent_path_or_name=None,
    )


async def authorize_hubspot(user_id, org_id):
    if not CLIENT_ID or CLIENT_ID == 'your_hubspot_client_id':
        raise HTTPException(status_code=400, detail='HubSpot CLIENT_ID is missing. Add it to backend/.env')
    if not CLIENT_SECRET or CLIENT_SECRET == 'your_hubspot_client_secret':
        raise HTTPException(status_code=400, detail='HubSpot CLIENT_SECRET is missing. Add it to backend/.env')

    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id,
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')

    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)

    params = {
        'client_id': CLIENT_ID,
        'scope': SCOPE,
        'redirect_uri': REDIRECT_URI,
        'state': encoded_state,
    }
    return f'{AUTHORIZATION_URL}?{urlencode(params)}'


async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail='Missing code or state in HubSpot callback.')

    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if saved_state and isinstance(saved_state, bytes):
        saved_state = saved_state.decode('utf-8')
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=response.text)

    token_data = response.json()
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(token_data), expire=3600)
    await delete_key_redis(f'hubspot_state:{org_id}:{user_id}')

    html = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=html)


async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No HubSpot credentials found.')
    if isinstance(credentials, bytes):
        credentials = credentials.decode('utf-8')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials


async def get_items_hubspot(credentials):
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    if not access_token:
        raise HTTPException(status_code=400, detail='No access token available for HubSpot.')

    headers = {'Authorization': f'Bearer {access_token}'}
    list_of_integration_item_metadata = []

    for object_name, object_label in [('contacts', 'Contact'), ('companies', 'Company'), ('deals', 'Deal')]:
        try:
            response = requests.get(
                f'https://api.hubapi.com/crm/v3/objects/{object_name}?limit=10&properties=dealname,name,company,firstname,lastname,email',
                headers=headers,
                timeout=20,
            )
            if response.status_code == 200:
                for item in response.json().get('results', []):
                    list_of_integration_item_metadata.append(
                        create_integration_item_metadata_object(item, object_label)
                    )
        except requests.RequestException:
            continue

    print(f'list_of_integration_item_metadata: {list_of_integration_item_metadata}')
    return list_of_integration_item_metadata
