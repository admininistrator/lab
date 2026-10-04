FROM python:3.10-slim
RUN pip install --no-cache-dir boto3
COPY s3lab.py /opt/s3lab.py
CMD ["sleep", "infinity"]