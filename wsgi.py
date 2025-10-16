# WSGI entrypoint for Gunicorn on Render
from app import create_app

# Gunicorn will look for `app` at module import time
app = create_app()