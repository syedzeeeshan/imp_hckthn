#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip and essential build tools
pip install --upgrade pip setuptools wheel

# Install your project dependencies
pip install -r requirements.txt

# Run database migrations (for Django)
python manage.py migrate
