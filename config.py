import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-change-in-production'
    MONGO_URI = os.environ.get('MONGO_URI')  # <-- Read from environment only in production
    if not MONGO_URI:
        MONGO_URI = 'mongodb://localhost:27017/tablemanager'  # fallback for local dev
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-change-me'