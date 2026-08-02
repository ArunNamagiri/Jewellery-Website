FROM python:3.12-slim

WORKDIR /app

# System deps for mysqlclient-less builds (PyMySQL is pure Python, but
# keep this minimal and add build-essential only if you swap drivers later)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p static/uploads

EXPOSE 5000

# gunicorn runs the app; app.py's init_db() only runs under `python app.py`,
# so entrypoint.sh (below) creates tables once before handing off to gunicorn
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
