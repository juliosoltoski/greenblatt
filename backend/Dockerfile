FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/opt/greenblatt/src

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
COPY src /opt/greenblatt/src
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

COPY backend /app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && uvicorn config.asgi:application --host 0.0.0.0 --port 8000"]
