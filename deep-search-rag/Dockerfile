# Build Backend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    tar \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src

# Create empty .env file to avoid errors if not provided at runtime
RUN touch .env

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Download and install Qdrant binary
RUN wget https://github.com/qdrant/qdrant/releases/download/v1.13.4/qdrant-x86_64-unknown-linux-musl.tar.gz && \
    tar -xzf qdrant-x86_64-unknown-linux-musl.tar.gz && \
    mv qdrant /usr/local/bin/ && \
    rm qdrant-x86_64-unknown-linux-musl.tar.gz

# Make entrypoint executable
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8001
ENV HOST=0.0.0.0

# Expose the port
EXPOSE 8001

# Start the application
CMD ["/app/entrypoint.sh"]