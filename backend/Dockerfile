# syntax=docker/dockerfile:1.7
#
# Backend image — Python 3.11 slim + FastAPI + OR-Tools + psycopg (Postgres driver).
# Runtime-only image; the test deps are not installed so the image stays lean.

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install runtime dependencies. ortools and psycopg both ship binary wheels for
# linux/amd64 + linux/arm64, so no compiler is required.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application code — copied last so iterating on code doesn't bust the pip layer.
COPY app ./app

EXPOSE 8000

# DATABASE_URL is read from the environment at startup (see app/database.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
