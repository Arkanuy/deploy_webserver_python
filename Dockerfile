FROM selenium/standalone-chrome:latest

USER root

# Install Python and pip with specific versions
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements file first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set up environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 8000

# Switch back to non-root user
USER seluser

# Command to run the application
CMD ["python3", "main.py"]
