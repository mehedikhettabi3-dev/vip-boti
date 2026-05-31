#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WSGI entry point for Gunicorn
Usage: gunicorn -w 4 -b 0.0.0.0:10000 wsgi:app
"""
import os
import sys

# Ensure UTF-8 encoding
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import the Flask app
from app import app

if __name__ == "__main__":
    app.run()
