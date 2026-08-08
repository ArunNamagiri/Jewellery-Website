#!/bin/sh
set -e

echo "Initializing database (creates tables if they don't exist)..."
python -c "import app; app.init_db()"
echo "Starting server with Google Authenticator OTP and live gold rates..."
exec gunicorn --bind 0.0.0.0:5000 --workers 3 --timeout 60 realtime_rates:app
