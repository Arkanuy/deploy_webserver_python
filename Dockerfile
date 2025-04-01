FROM selenium/standalone-chrome:latest

USER root

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy your application files
COPY . .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Switch back to non-root user
USER seluser

# Command to run the application
CMD ["python3", "main.py"]
