# Base image with Python
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy app files
COPY . .

# Install Python packages
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browser binaries
RUN playwright install chromium

# Expose the port for Flask
ENV PORT=10000

# Start your Flask app
CMD ["python", "main.py"]
