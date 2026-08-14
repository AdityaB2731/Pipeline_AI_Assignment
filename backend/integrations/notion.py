# notion.py

import json
import os
import secrets
from dotenv import load_dotenv
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv()

CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()

REDIRECT_URI = 'http://localhost:8000/integrations/notion/oauth2callback'
authorization_url = f'https://api.notion.com/v1/oauth/authorize?client_id={CLIENT_ID}&response_type=code&owner=user&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fintegrations%2Fnotion%2Foauth2callback'

async def authorize_notion(user_id, org_id):
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=400, detail='Notion CLIENT_ID or CLIENT_SECRET missing in backend/.env')
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'notion_state:{org_id}:{user_id}', encoded_state, expire=600)

    return f'{authorization_url}&state={encoded_state}'

async def oauth2callback_notion(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(encoded_state)

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'notion_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                'https://api.notion.com/v1/oauth/token',
                json={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI
                }, 
                headers={
                    'Authorization': f'Basic {encoded_client_id_secret}',
                    'Content-Type': 'application/json',
                }
            ),
            delete_key_redis(f'notion_state:{org_id}:{user_id}'),
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=response.text)

    await add_key_value_redis(f'notion_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_notion_credentials(user_id, org_id):
    credentials = await get_value_redis(f'notion_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    await delete_key_redis(f'notion_credentials:{org_id}:{user_id}')

    return credentials

def _recursive_dict_search(data, target_key):
    """Recursively search for a key in a dictionary of dictionaries."""
    if target_key in data:
        return data[target_key]

    for value in data.values():
        if isinstance(value, dict):
            result = _recursive_dict_search(value, target_key)
            if result is not None:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _recursive_dict_search(item, target_key)
                    if result is not None:
                        return result
    return None

def create_integration_item_metadata_object(
    response_json: dict,
) -> IntegrationItem:
    """creates an integration metadata object from the response"""
    properties = response_json.get('properties', {})
    name = _recursive_dict_search(properties, 'content') if properties else None

    parent = response_json.get('parent', {})
    parent_type = parent.get('type') or ''
    if parent_type == 'workspace':
        parent_id = None
    elif parent_type:
        parent_id = parent.get(parent_type)
    else:
        parent_id = None

    if name is None and response_json.get('object') == 'database':
        title = response_json.get('title', [])
        if title and isinstance(title[0], dict):
            name = title[0].get('plain_text', 'Untitled database')

    name = _recursive_dict_search(response_json, 'content') if name is None else name
    name = response_json.get('object', 'item') if name is None else name
    name = f"{response_json.get('object', 'item')} {name}"

    integration_item_metadata = IntegrationItem(
        id=response_json.get('id'),
        type=response_json.get('object'),
        name=name,
        creation_time=response_json.get('created_time'),
        last_modified_time=response_json.get('last_edited_time'),
        parent_id=parent_id,
    )

    return integration_item_metadata

async def get_items_notion(credentials) -> list[IntegrationItem]:
    """Aggregates all metadata relevant for a notion integration"""
    credentials = json.loads(credentials)
    response = requests.post(
        'https://api.notion.com/v1/search',
        headers={
            'Authorization': f'Bearer {credentials.get("access_token")}',
            'Notion-Version': '2022-06-28',
        },
    )

    if response.status_code == 200:
        results = response.json()['results']
        list_of_integration_item_metadata = []
        for result in results:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(result)
            )

        print(f'list_of_integration_item_metadata: {list_of_integration_item_metadata}')
        return list_of_integration_item_metadata

    raise HTTPException(status_code=400, detail=response.text)
