# syntax=docker/dockerfile:1

# 1) Start from a lightweight Python image
FROM python:3.12-slim AS base

# 2) Prevent Python from writing .pyc files and keep output unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3) Set the working directory inside the container
WORKDIR /app

# 4) Copy the dependency list first and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5) Copy the rest of the application code
COPY . .

# 6) Default environment settings (override in docker-compose or env file)
ENV FLASK_APP=app.py \
    ENV=production \
    AUTO_CREATE_SCHEMA=0

# 7) Expose the port Gunicorn will listen on
EXPOSE 8000

# 8) Run the app with Gunicorn in production mode
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:create_app()"]
