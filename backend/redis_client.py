import os
from urllib.parse import quote

from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

redis_host = quote(os.environ.get('REDIS_HOST', 'localhost'), safe='')
redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

async def add_key_value_redis(key, value, expire=None):
    await redis_client.set(key, value)
    if expire:
        await redis_client.expire(key, expire)

async def get_value_redis(key):
    return await redis_client.get(key)

async def delete_key_redis(key):
    await redis_client.delete(key)
