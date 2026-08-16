FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY services/service-a/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El modulo de telemetria es compartido por los dos servicios.
COPY services/common/ /app/common/
COPY services/service-a/app.py /app/app.py

# Usuario sin privilegios.
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser

ENV DB_PATH=/tmp/service_a.db
EXPOSE 8001 9464

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:'+os.getenv('PORT','8001')+'/health')"

CMD ["python", "app.py"]
