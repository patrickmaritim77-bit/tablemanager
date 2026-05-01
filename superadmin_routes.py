from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from extensions import mongo
from models import (
    create_tenant, get_tenant_by_email, get_tenant_summary,
    add_member, get_members_of_tenant,            # still needed for GET monitoring
    record_contribution, get_contributions_tenant, # still needed for GET monitoring
    create_notification, get_notifications_for_tenant
)

superadmin_bp = Blueprint('superadmin', __name__)

def superadmin_required():
    identity = get_jwt_identity()
    if identity['role'] != 'superadmin':
        return jsonify({'msg': 'Superadmin only'}), 403
    return None

@superadmin_bp.before_request
@jwt_required()
def check_superadmin():
    return superadmin_required()

# ---------- TENANT ADMINISTRATION ----------
@superadmin_bp.route('/tenants', methods=['GET'])
def list_tenants():
    tenants = list(mongo.db.tenants.find({}, {'chairperson_password_hash': 0}))
    for t in tenants:
        t['_id'] = str(t['_id'])
        t['trial_end_date'] = t['trial_end_date'].isoformat() if 'trial_end_date' in t else None
        t['created_at'] = t['created_at'].isoformat() if 'created_at' in t else None
        summary = get_tenant_summary(mongo, t['_id'])
        t.update(summary)
    return jsonify(tenants), 200

@superadmin_bp.route('/tenants', methods=['POST'])
def create_new_tenant():
    data = request.get_json()
    required = ['department_name', 'chairperson_email', 'password', 'trial_days']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Missing fields'}), 400
    if get_tenant_by_email(mongo, data['chairperson_email']):
        return jsonify({'msg': 'Email already registered'}), 400
    res = create_tenant(mongo, data['department_name'], data['chairperson_email'],
                       data['password'], int(data['trial_days']))
    return jsonify({'msg': 'Tenant created', 'id': str(res.inserted_id)}), 201

@superadmin_bp.route('/tenants/<tenant_id>', methods=['PUT'])
def update_tenant(tenant_id):
    data = request.get_json()
    update_fields = {}
    if 'trial_days' in data:
        trial_end = datetime.utcnow() + timedelta(days=int(data['trial_days']))
        update_fields['trial_end_date'] = trial_end
    if 'is_active' in data:
        update_fields['is_active'] = data['is_active']
    if 'department_name' in data:
        update_fields['department_name'] = data['department_name']
    if 'password' in data:
        update_fields['chairperson_password_hash'] = generate_password_hash(data['password'])
    mongo.db.tenants.update_one({'_id': ObjectId(tenant_id)}, {'$set': update_fields})
    return jsonify({'msg': 'Tenant updated'}), 200

@superadmin_bp.route('/tenants/<tenant_id>', methods=['DELETE'])
def delete_tenant(tenant_id):
    mongo.db.tenants.delete_one({'_id': ObjectId(tenant_id)})
    mongo.db.members.delete_many({'tenant_id': ObjectId(tenant_id)})
    mongo.db.contributions.delete_many({'tenant_id': ObjectId(tenant_id)})
    mongo.db.loans.delete_many({'tenant_id': ObjectId(tenant_id)})
    mongo.db.projects.delete_many({'tenant_id': ObjectId(tenant_id)})
    mongo.db.notifications.delete_many({'tenant_id': ObjectId(tenant_id)})
    return jsonify({'msg': 'Tenant and all related data removed'}), 200

# ---------- MONITORING (read-only) ----------
@superadmin_bp.route('/tenants/<tenant_id>/members', methods=['GET'])
def list_tenant_members(tenant_id):
    members = get_members_of_tenant(mongo, ObjectId(tenant_id))
    for m in members:
        m['_id'] = str(m['_id'])
        m['tenant_id'] = str(m['tenant_id'])
        if 'join_date' in m:
            m['join_date'] = m['join_date'].isoformat()
    return jsonify(members), 200

@superadmin_bp.route('/tenants/<tenant_id>/contributions', methods=['GET'])
def list_tenant_contributions(tenant_id):
    contribs = get_contributions_tenant(mongo, ObjectId(tenant_id))
    for c in contribs:
        c['_id'] = str(c['_id'])
        c['tenant_id'] = str(c['tenant_id'])
        c['member_id'] = str(c['member_id'])
        c['date'] = c['date'].isoformat()
    return jsonify(contribs), 200

# ---------- NOTIFICATIONS (send only) ----------
@superadmin_bp.route('/notifications', methods=['POST'])
def send_notification():
    data = request.get_json()
    required = ['tenant_id', 'message']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Missing fields'}), 400
    create_notification(mongo, ObjectId(data['tenant_id']), data['message'],
                        sender=data.get('sender', 'superadmin'))
    return jsonify({'msg': 'Notification sent'}), 201

@superadmin_bp.route('/notifications/reminder', methods=['POST'])
def send_reminder():
    data = request.get_json()
    required = ['tenant_id', 'message']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Missing fields'}), 400
    create_notification(mongo, ObjectId(data['tenant_id']),
                        f"⏰ Reminder: {data['message']}", sender='superadmin')
    return jsonify({'msg': 'Reminder sent'}), 201

@superadmin_bp.route('/tenants/<tenant_id>/notifications', methods=['GET'])
def view_tenant_notifications(tenant_id):
    notifs = get_notifications_for_tenant(mongo, ObjectId(tenant_id))
    for n in notifs:
        n['_id'] = str(n['_id'])
        n['tenant_id'] = str(n['tenant_id'])
        n['created_at'] = n['created_at'].isoformat()
    return jsonify(notifs), 200