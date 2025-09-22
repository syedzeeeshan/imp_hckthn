#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip and build tools
pip install --upgrade pip
pip install setuptools wheel

# Install your dependencies
pip install -r requirements.txt

# Run your migrations (for Django)
python manage.py migrate
