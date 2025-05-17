# Use official Playwright image with Python & Chromium
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Add French language and time
RUN apt-get update && \
    apt-get install -y locales && \
    locale-gen fr_FR.UTF-8 && \
    update-locale LANG=fr_FR.UTF-8
ENV LANG fr_FR.UTF-8
ENV LANGUAGE fr_FR:fr
ENV LC_ALL fr_FR.UTF-8

# Install Playwright browser (Chromium only)
RUN playwright install chromium

ENV PORT=10000

CMD ["python", "main.py"]
