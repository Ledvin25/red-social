#!/bin/bash

# Run tests
pytest --cov=main --cov-report=xml --junitxml=test-results.xml

# Keep the container running
exec gunicorn -w 4 -b 0.0.0.0:8000 main:app