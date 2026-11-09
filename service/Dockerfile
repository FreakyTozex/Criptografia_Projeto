FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py client.py crypto_tools.py tls_probe.py file_transfer.py ./
COPY entrypoint.sh /entrypoint.sh
RUN useradd --create-home --uid 10001 poc && mkdir -p /data /keys /run/poc-certs && chown poc:poc /data /keys /run/poc-certs
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8443 8444
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
