FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set Python path to find modules at /app
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Create directory for SQLite database persistence
RUN mkdir -p /app/data

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# No CMD here — fly.toml processes will start the right commands
