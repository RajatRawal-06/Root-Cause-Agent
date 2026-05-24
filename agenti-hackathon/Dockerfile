FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV INCIDENT_DB_PATH=/app/data/incidents.db

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY backend backend
COPY frontend frontend
COPY README.md IMPLEMENTATION_PLAN.md ./

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "backend/server.py"]
