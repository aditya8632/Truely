FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . /app

RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir .

EXPOSE 8000

