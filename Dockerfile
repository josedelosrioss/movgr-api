FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 8000

# Single worker on purpose: the metro snapshot and connected WebSocket clients live in
# process memory, so the app must not be replicated within one container.
CMD ["uvicorn", "src.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--ws-ping-interval", "20", "--ws-ping-timeout", "20"]
