FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src
COPY .env ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Make start script executable
RUN mkdir -p /app/scripts
COPY start.sh /app/scripts/
RUN chmod +x /app/scripts/start.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8004
ENV HOST=0.0.0.0

# Expose the port
EXPOSE 8004

# Start the application
CMD ["/app/scripts/start.sh"]