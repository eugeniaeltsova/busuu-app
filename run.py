"""
run.py — start the app from the project root.
Usage: python run.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
