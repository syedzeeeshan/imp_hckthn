"""
Django settings for Campus Club Management Suite
"""
import os

# Environment-specific settings
if os.environ.get('ENVIRONMENT', 'development') == 'production':
    from .production import *
else:
    from .development import *
