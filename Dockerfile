FROM python:3.11-slim

# Install Chromium + Playwright deps
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-noto-cjk \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdrm2 \
    libgbm1 libgtk-3-0 libnspr4 libnss3 libxcomposite1 libxdamage1 \
    libxrandr2 xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install playwright && playwright install --with-deps chromium

COPY backend/ /app/

ENV PYTHONUNBUFFERED=1
ENV PORT=5001
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV QUARK_STATE_PATH=/etc/secrets/quark_state.json

EXPOSE 5001

CMD ["python", "server.py"]