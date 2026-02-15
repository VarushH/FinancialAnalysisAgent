# Base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# poppler-utils is required for PDF processing (if using pdf2image or similar)
# curl is required for healthcheck
RUN apt-get update && apt-get install -y \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
# Since context is root, we copy the backend folder contents to /app
COPY backend /app/

# Expose port
EXPOSE 8000

# Run migrations then start server (inline, no shell script needed)
CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
