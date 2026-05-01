from flask import Flask, render_template
from config import Config
from extensions import mongo, jwt
from auth import auth_bp
from superadmin_routes import superadmin_bp
from tenant_routes import tenant_bp
from models import create_superadmin_if_not_exists, create_demo_tenant_if_not_exists
import ssl

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Create a custom SSL context that forces TLS 1.2 and skips all validation
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2   # Atlas requires TLS 1.2

    app.config["MONGO_OPTIONS"] = {
        "tls": True,
        "tlsAllowInvalidCertificates": True,
        "tlsAllowInvalidHostnames": True,
        "ssl": True,                           # older PyMongo compatibility
        "ssl_cert_reqs": ssl.CERT_NONE,
        "ssl_check_hostname": False,
        "ssl_context": ctx                      # <-- This forces TLS 1.2
    }

    mongo.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(superadmin_bp, url_prefix='/api/superadmin')
    app.register_blueprint(tenant_bp, url_prefix='/api/tenant')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/superadmin')
    def superadmin_page():
        return render_template('superadmin.html')

    @app.route('/tenant')
    def tenant_page():
        return render_template('tenant.html')

    with app.app_context():
        create_superadmin_if_not_exists(mongo)
        create_demo_tenant_if_not_exists(mongo)

    return app

app = create_app()