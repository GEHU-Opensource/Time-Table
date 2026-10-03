FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    WEB_WORKERS=3 \
    FORWARDED_ALLOW_IPS=127.0.0.1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app \
    && chown app:app /app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=app:app . /app

RUN ENV=prod \
    SECURE=true \
    SECRET_KEY=build-only-collectstatic-key-5d1f9c3a7e2b4860fa6c0d9e8b7a4c21 \
    BASE_DOMAIN=example.invalid \
    DATABASE_URL=postgres://x:x@localhost/x \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles \
    && chmod +x /app/deploy/entrypoint.sh

USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import os, sys, urllib.request; req = urllib.request.Request('http://127.0.0.1:8000/healthz/', headers={'Host': 'healthz.' + os.environ['BASE_DOMAIN'], 'X-Forwarded-Proto': 'https'}); sys.exit(0 if urllib.request.urlopen(req, timeout=4).status == 200 else 1)"]

ENTRYPOINT ["/app/deploy/entrypoint.sh", "web"]

CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${WEB_WORKERS} --forwarded-allow-ips ${FORWARDED_ALLOW_IPS} --timeout 60 --graceful-timeout 30 --max-requests 2000 --max-requests-jitter 200 --access-logfile - --error-logfile -"]
