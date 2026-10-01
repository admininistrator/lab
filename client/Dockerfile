FROM python:3.12-slim

RUN pip install --no-cache-dir boto3

WORKDIR /opt

COPY s3lab.py /opt/s3lab.py

CMD ["sleep", "infinity"]
