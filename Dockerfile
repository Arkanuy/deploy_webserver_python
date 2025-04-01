FROM python:3.9-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install matching ChromeDriver for Chrome 134
RUN wget -q "https://storage.googleapis.com/chrome-for-testing-public/134.0.6052.0/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    && rm -rf chromedriver-linux64.zip chromedriver-linux64 \
    && chmod +x /usr/local/bin/chromedriver

# Set up working directory
WORKDIR /app

# Copy files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the application
CMD ["python", "main.py"]
