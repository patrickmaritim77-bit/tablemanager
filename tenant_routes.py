from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from models import (
    add_member, get_members_of_tenant,
    record_contribution, get_contributions_tenant,
    create_loan, get_loans_tenant, add_loan_repayment,
    create_project, contribute_to_project, get_projects_tenant,
    get_notifications_for_tenant
)
from extensions import mongo

tenant_bp = Blueprint('tenant', __name__)

def get_tenant_id():
    identity = get_jwt_identity()
    if identity['role'] != 'tenant':
        return None
    return ObjectId(identity['tenant_id'])

@tenant_bp.before_request
@jwt_required()
def check_tenant():
    if get_tenant_id() is None:
        return jsonify({'msg': 'Tenant access required'}), 403

# Dashboard (current)
@tenant_bp.route('/dashboard', methods=['GET'])
def dashboard():
    tid = get_tenant_id()
    members_count = mongo.db.members.count_documents({'tenant_id': tid})
    contrib_total = sum(c['amount'] for c in mongo.db.contributions.find({'tenant_id': tid}))
    active_loans = mongo.db.loans.count_documents({'tenant_id': tid, 'status': 'active'})
    projects_count = mongo.db.projects.count_documents({'tenant_id': tid})
    unread_notifs = mongo.db.notifications.count_documents({'tenant_id': tid, 'read': False})
    return jsonify({
        'members': members_count,
        'total_contributions': contrib_total,
        'active_loans': active_loans,
        'projects': projects_count,
        'unread_notifications': unread_notifs
    }), 200

# Charts endpoint – returns aggregated data for graphs
@tenant_bp.route('/dashboard/charts', methods=['GET'])
def chart_data():
    tid = get_tenant_id()
    # Contributions per member
    pipeline = [
        {'$match': {'tenant_id': tid}},
        {'$group': {'_id': '$member_id', 'total': {'$sum': '$amount'}}}
    ]
    contrib_agg = list(mongo.db.contributions.aggregate(pipeline))
    # Map member IDs to names
    members = {str(m['_id']): f"{m['first_name']} {m['last_name']}" for m in mongo.db.members.find({'tenant_id': tid})}
    contrib_by_member = [{'member': members.get(str(c['_id']), 'Unknown'), 'total': c['total']} for c in contrib_agg]

    # Loan status counts
    active_loans = mongo.db.loans.count_documents({'tenant_id': tid, 'status': 'active'})
    repaid_loans = mongo.db.loans.count_documents({'tenant_id': tid, 'status': 'repaid'})
    # Contributions over time (last 12 months by month)
    from datetime import datetime, timedelta
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    monthly = mongo.db.contributions.aggregate([
        {'$match': {'tenant_id': tid, 'date': {'$gte': one_year_ago}}},
        {'$group': {'_id': {'$substr': ['$date', 0, 7]}, 'total': {'$sum': '$amount'}}},
        {'$sort': {'_id': 1}}
    ])
    monthly_contrib = list(monthly)

    return jsonify({
        'contrib_by_member': contrib_by_member,
        'loan_status': {'active': active_loans, 'repaid': repaid_loans},
        'monthly_contributions': monthly_contrib
    }), 200

# Members CRUD (unchanged)
@tenant_bp.route('/members', methods=['GET'])
def list_members():
    tid = get_tenant_id()
    members = get_members_of_tenant(mongo, tid)
    for m in members:
        m['_id'] = str(m['_id'])
        m['tenant_id'] = str(m['tenant_id'])
        if 'join_date' in m:
            m['join_date'] = m['join_date'].isoformat()
    return jsonify(members), 200

@tenant_bp.route('/members', methods=['POST'])
def create_member():
    tid = get_tenant_id()
    data = request.get_json()
    required = ['first_name', 'last_name', 'email', 'phone']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Missing member fields'}), 400
    add_member(mongo, tid, data)
    return jsonify({'msg': 'Member added'}), 201

@tenant_bp.route('/members/<member_id>', methods=['PUT'])
def update_member(member_id):
    tid = get_tenant_id()
    data = request.get_json()
    mongo.db.members.update_one({'_id': ObjectId(member_id), 'tenant_id': tid}, {'$set': data})
    return jsonify({'msg': 'Updated'}), 200

@tenant_bp.route('/members/<member_id>', methods=['DELETE'])
def delete_member(member_id):
    tid = get_tenant_id()
    mongo.db.members.delete_one({'_id': ObjectId(member_id), 'tenant_id': tid})
    return jsonify({'msg': 'Deleted'}), 200

# Contributions (unchanged)
@tenant_bp.route('/contributions', methods=['GET'])
def list_contributions():
    tid = get_tenant_id()
    contribs = get_contributions_tenant(mongo, tid)
    for c in contribs:
        c['_id'] = str(c['_id'])
        c['tenant_id'] = str(c['tenant_id'])
        c['member_id'] = str(c['member_id'])
        c['date'] = c['date'].isoformat()
    return jsonify(contribs), 200

@tenant_bp.route('/contributions', methods=['POST'])
def post_contribution():
    tid = get_tenant_id()
    data = request.get_json()
    if 'member_id' not in data or 'amount' not in data:
        return jsonify({'msg': 'Missing fields'}), 400
    record_contribution(mongo, tid, ObjectId(data['member_id']), float(data['amount']))
    return jsonify({'msg': 'Contribution recorded'}), 201

# Loans (unchanged)
@tenant_bp.route('/loans', methods=['GET'])
def list_loans():
    tid = get_tenant_id()
    loans = get_loans_tenant(mongo, tid)
    for l in loans:
        l['_id'] = str(l['_id'])
        l['tenant_id'] = str(l['tenant_id'])
        l['member_id'] = str(l['member_id'])
        l['start_date'] = l['start_date'].isoformat()
        l['due_date'] = l['due_date'].isoformat()
        for r in l['repayments']:
            r['date'] = r['date'].isoformat()
    return jsonify(loans), 200

@tenant_bp.route('/loans', methods=['POST'])
def issue_loan():
    tid = get_tenant_id()
    data = request.get_json()
    required = ['member_id', 'principal', 'interest_rate', 'duration_days']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Missing loan fields'}), 400
    create_loan(mongo, tid, ObjectId(data['member_id']),
                float(data['principal']), float(data['interest_rate']),
                int(data['duration_days']))
    return jsonify({'msg': 'Loan issued'}), 201

@tenant_bp.route('/loans/<loan_id>/repay', methods=['POST'])
def repay_loan(loan_id):
    tid = get_tenant_id()
    data = request.get_json()
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'msg': 'Invalid amount'}), 400
    add_loan_repayment(mongo, ObjectId(loan_id), amount)
    return jsonify({'msg': 'Repayment recorded'}), 200

# Projects (unchanged)
@tenant_bp.route('/projects', methods=['GET'])
def list_projects():
    tid = get_tenant_id()
    projects = get_projects_tenant(mongo, tid)
    for p in projects:
        p['_id'] = str(p['_id'])
        p['tenant_id'] = str(p['tenant_id'])
        p['start_date'] = p['start_date'].isoformat() if 'start_date' in p else None
        for c in p['contributions']:
            c['member_id'] = str(c['member_id'])
            c['date'] = c['date'].isoformat() if 'date' in c else None
    return jsonify(projects), 200

@tenant_bp.route('/projects', methods=['POST'])
def new_project():
    tid = get_tenant_id()
    data = request.get_json()
    required = ['name', 'description', 'budget']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Missing project fields'}), 400
    create_project(mongo, tid, {'name': data['name'], 'description': data['description'], 'budget': float(data['budget'])})
    return jsonify({'msg': 'Project created'}), 201

@tenant_bp.route('/projects/<project_id>/contribute', methods=['POST'])
def project_contribute(project_id):
    tid = get_tenant_id()
    data = request.get_json()
    if 'member_id' not in data or 'amount' not in data:
        return jsonify({'msg': 'Missing fields'}), 400
    contribute_to_project(mongo, ObjectId(project_id), ObjectId(data['member_id']), float(data['amount']))
    return jsonify({'msg': 'Contribution recorded'}), 200

# Notifications for the tenant
@tenant_bp.route('/notifications', methods=['GET'])
def tenant_notifications():
    tid = get_tenant_id()
    notifs = get_notifications_for_tenant(mongo, tid)
    for n in notifs:
        n['_id'] = str(n['_id'])
        n['tenant_id'] = str(n['tenant_id'])
        n['created_at'] = n['created_at'].isoformat()
    return jsonify(notifs), 200

@tenant_bp.route('/notifications/read', methods=['POST'])
def mark_notifications_read():
    tid = get_tenant_id()
    mongo.db.notifications.update_many({'tenant_id': tid, 'read': False}, {'$set': {'read': True}})
    return jsonify({'msg': 'Notifications marked as read'}), 200