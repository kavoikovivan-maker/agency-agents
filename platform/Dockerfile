FROM python:3.13-slim
WORKDIR /app
COPY platform/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
ENV APP_DATA_DIR=/data
RUN mkdir -p /data/uploads
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).status==200 else 1)"
WORKDIR /app/platform/backend
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]
