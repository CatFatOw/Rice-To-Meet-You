import os
from pathlib import Path
from celery import Celery
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

redis_url = os.environ["REDIS_URL"]

# Celery's Redis result backend requires this TLS option for a rediss:// URL.
celery_redis_url = redis_url
if celery_redis_url.startswith("rediss://") and "ssl_cert_reqs=" not in celery_redis_url:
    separator = "&" if "?" in celery_redis_url else "?"
    celery_redis_url = f"{celery_redis_url}{separator}ssl_cert_reqs=CERT_REQUIRED"

celery_app = Celery(
    "rice_to_meet_you",
    broker=celery_redis_url,
    backend=celery_redis_url,
)

celery_app.conf.imports = (
    "cache.prewarm_visitor",
)
