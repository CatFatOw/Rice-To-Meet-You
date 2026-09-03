"""File handles the redis caching of the visitor data on a redis cache server. Super fast cache """
from dotenv import load_dotenv
import redis
import json
import os
from repository.final_visitor_repository import VisitorRepository
from datetime import date, datetime


redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise Exception("Please provide a redis_url in the .env file")

redis_client = redis.from_url(redis_url, decode_responses=True)

# intialize the repository key
def visitor_cache_key(city: str, requested_date: date) -> str:
    return f"visitor:{city.strip().lower()}:{requested_date.isoformat()}"

def get_cached_visitors(city:str, requested_date:date):
    cached_value = redis_client.get(visitor_cache_key(city, requested_date))
    return json.loads(cached_value) if cached_value else None

def load_visitors(city: str, requested_date: date, visitors: list[dict]):
    # time limit to live: 12 hours
    redis_client.setex(visitor_cache_key(city, requested_date), 12*60*60, json.dumps(visitors))


