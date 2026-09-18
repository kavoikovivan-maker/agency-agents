FROM python:3.13-slim
WORKDIR /app
COPY platform/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
EXPOSE 8080
CMD ["uvicorn","platform.backend.main:app","--host","0.0.0.0","--port","8080"]
