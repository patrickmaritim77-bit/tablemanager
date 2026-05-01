from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from models import get_superadmin, get_tenant_by_email, tenant_is_trial_valid
from werkzeug.security import check_password_hash
from extensions import mongo   # ← now safe

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/superadmin/login', methods=['POST'])
def superadmin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    admin = get_superadmin(mongo)
    if admin and check_password_hash(admin['password_hash'], password):
        token = create_access_token(identity={'role': 'superadmin', 'username': username})
        return jsonify({'token': token}), 200
    return jsonify({'msg': 'Invalid credentials'}), 401

@auth_bp.route('/tenant/login', methods=['POST'])
def tenant_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    tenant = get_tenant_by_email(mongo, email)
    if tenant and check_password_hash(tenant['chairperson_password_hash'], password):
        if not tenant_is_trial_valid(tenant):
            return jsonify({'msg': 'Trial expired or account inactive'}), 403
        token = create_access_token(identity={'role': 'tenant', 'tenant_id': str(tenant['_id'])})
        return jsonify({'token': token, 'tenant_id': str(tenant['_id']), 'department': tenant['department_name']}), 200
    return jsonify({'msg': 'Invalid credentials'}), 401