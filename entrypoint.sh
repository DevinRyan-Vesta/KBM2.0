#!/bin/bash
set -e

echo "========================================"
echo "Starting KBM 2.0 Application"
echo "========================================"

# Wait a moment for any dependent services to be ready
sleep 2

# Run database migrations for master database
echo "Running master database migrations..."
python -m flask db upgrade -d migrations_master 2>/dev/null || echo "No master migrations to run or migrations not initialized"

# Create master database tables if needed
echo "Ensuring master database schema exists..."
python << 'PYTHON'
from app_multitenant import create_app
app = create_app()
with app.app_context():
    from utilities.master_database import master_db
    try:
        master_db.create_all()
        print("✓ Master database schema verified")
    except Exception as e:
        print(f"✗ Error creating master database schema: {e}")
        exit(1)
PYTHON

# Print startup information
echo "========================================"
echo "Configuration:"
echo "  Environment: ${ENV:-production}"
echo "  Port: ${PORT:-8000}"
echo "  Python: $(python --version)"
echo "========================================"

# Start gunicorn with production settings
echo "Starting Gunicorn server..."
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WORKERS:-4} \
    --worker-class sync \
    --timeout ${TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info} \
    --preload \
    app_multitenant:app
