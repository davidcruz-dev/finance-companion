# Use Python 3.10 slim image for smaller size
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bitcoin_trading_bot.py .

# Create non-root user for security
RUN useradd -m -u 1001 botuser && chown -R botuser:botuser /app
USER botuser

# Health check removed for Railway deployment

# Run the bot
CMD ["python", "bitcoin_trading_bot.py"]