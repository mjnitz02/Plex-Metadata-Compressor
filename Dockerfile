FROM python:3.12-alpine
RUN apk add --no-cache pngquant
RUN pip install --no-cache-dir pillow
WORKDIR /app
COPY compress.py .
ENTRYPOINT ["python", "-u", "/app/compress.py"]
