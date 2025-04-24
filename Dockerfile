# Use official Playwright image with Python & Chromium
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browser (Chromium only)
RUN playwright install chromium

ENV PORT=10000

CMD ["python", "main.py"]
