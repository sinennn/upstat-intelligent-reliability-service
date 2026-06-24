FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

COPY . /app

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV UPSTAT_GRPC_ADDRESS=upstat_backend:8080


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
