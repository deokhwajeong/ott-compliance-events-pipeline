FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

ENV DATABASE_URL=sqlite:////app/data/ott_compliance.db \
    MODEL_DIR=/app/data/models
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
