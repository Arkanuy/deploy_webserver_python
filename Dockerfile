FROM python:3.9-slim

# Install dependencies untuk Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y \
       google-chrome-stable \
       chromedriver \
       fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy aplikasi
COPY . .

# Set environment variable untuk Chrome
ENV DISPLAY=:99
ENV PATH="/usr/bin/chromedriver:${PATH}"

CMD ["python", "main.py"]
