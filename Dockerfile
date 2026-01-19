# Dockerfile for Ambacar Notification Service
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

# Copy project
COPY . .

# ARG para collectstatic durante build (valor dummy, no se usa en runtime)
ARG SECRET_KEY=dummy-secret-key-for-build-only
ARG DATABASE_URL=sqlite:///db.sqlite3

# Collect static files (usa los ARG temporales)
RUN SECRET_KEY=${SECRET_KEY} DATABASE_URL=${DATABASE_URL} python manage.py collectstatic --noinput

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default command
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
