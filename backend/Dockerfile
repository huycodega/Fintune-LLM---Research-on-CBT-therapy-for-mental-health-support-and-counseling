FROM python:3.11-slim

# system deps for psycopg + cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ARG REQUIREMENTS_FILE=requirements.txt
COPY requirements*.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r ${REQUIREMENTS_FILE}

COPY . .

EXPOSE 8000
# Apply DB migrations, then serve. $PORT is injected by Railway/Render;
# defaults to 8000 for local docker-compose. (The cron service overrides this
# command, so it is unaffected.)
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
