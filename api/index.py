import sys
import os

# Add the project root to sys.path so Vercel can find the 'app' module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# This file is used by Vercel to mount the FastAPI application.
