FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
ENV DB_PATH=/data/foodbridge.db
CMD ["gunicorn","-b","0.0.0.0:8080","app:app"]
