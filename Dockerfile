FROM python:3.9-slim

# Install required packages
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "main.py"]
