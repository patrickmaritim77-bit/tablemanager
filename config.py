import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-change-in-production')
    MONGO_URI = os.environ['MONGO_URI']   # Raises KeyError if not set – so you know immediately
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-me')