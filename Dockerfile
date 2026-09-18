# Python 3.11 is pinned deliberately: geopandas, pykrige and psycopg2-binary do not
# reliably publish wheels for the newest interpreters, and an unpinned base would
# turn a routine redeploy into a source build.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copied before the source so dependency layers stay cached across code changes.
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# main.py imports its siblings flatly ("import database", "from repository... import"),
# so the app directory has to BE the working directory -- "uvicorn app.main:app" from
# the repo root does not work.
COPY app/ /app/

EXPOSE 8000

# Railway injects PORT; the fallback keeps `docker run` working locally.
# A single worker is intentional: the SQLAlchemy pool is per-process and this service
# shares its Neon database with another deployment.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
