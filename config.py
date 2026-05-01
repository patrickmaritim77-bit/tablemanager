import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-change-in-production')
    # Use the Atlas connection that worked in Compass
    MONGO_URI = os.environ.get(
        'MONGO_URI',
        'mongodb+srv://root:YOUR-REAL-PASSWORD@cluster0g.scevxks.mongodb.net/tablemanager?tls=true&tlsAllowInvalidCertificates=true'
    )
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-me')