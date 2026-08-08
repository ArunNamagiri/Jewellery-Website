#!/bin/sh
set -e

echo "Initializing database (creates tables if they don't exist)..."
python -c "import app; app.init_db()"
echo "Initializing Google Authenticator OTP..."
python -c "import otp_entrypoint"
echo "Starting server..."
exec gunicorn --bind 0.0.0.0:5000 --workers 3 --timeout 60 app:app
