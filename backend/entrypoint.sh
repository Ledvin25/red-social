#!/bin/bash

# Retry mechanism to ensure PostgreSQL is ready
function wait_for_postgres() {
    retries=5
    while [ $retries -gt 0 ]; do
        pg_isready -h db -U myuser
        if [ $? -eq 0 ]; then
            echo "PostgreSQL is ready"
            return 0
        fi
        echo "Waiting for PostgreSQL to be ready..."
        retries=$((retries-1))
        sleep 5
    done
    echo "PostgreSQL is not ready"
    exit 1
}

# Wait for PostgreSQL to be ready
wait_for_postgres

# Run tests
pytest --cov=main --cov-report=xml --junitxml=test-results.xml

# Keep the container running
exec gunicorn -w 4 -b 0.0.0.0:8000 main:app