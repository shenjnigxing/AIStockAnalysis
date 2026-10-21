FROM python:3.11-slim

WORKDIR /app
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Existing app.services modules re-export implementation packages from
# services/*; the original Dockerfile did not copy them, causing import errors.
COPY services /opt/services
ENV PYTHONPATH="/app:/opt/services/backtest-engine:/opt/services/broker-adapter:/opt/services/data-ingest:/opt/services/notification-service:/opt/services/paper-trading:/opt/services/recommendation-engine:/opt/services/risk-engine:/opt/services/screener:/opt/services/strategy-engine"

COPY apps/api /app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
