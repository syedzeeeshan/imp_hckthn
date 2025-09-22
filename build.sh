#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Upgrade pip and essential build tools
pip install --upgrade pip setuptools wheel

# 2. Install your project dependencies
pip install -r requirements.txt

# 3. Run database migrations (for Django)
python manage.py migrate
