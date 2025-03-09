# Build Backend
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

# Create empty .env file to avoid errors if not provided at runtime
RUN touch .env

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Make entrypoint executable
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8002
ENV HOST=0.0.0.0

# Expose the port
EXPOSE 8002

# Start the application
CMD ["/app/entrypoint.sh"]