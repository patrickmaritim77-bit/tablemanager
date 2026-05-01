from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

def create_superadmin_if_not_exists(mongo):
    if mongo.db.superadmins.count_documents({}) == 0:
        mongo.db.superadmins.insert_one({
            'username': 'superadmin',
            'password_hash': generate_password_hash('admin123')
        })

def get_superadmin(mongo):
    return mongo.db.superadmins.find_one({'username': 'superadmin'})

# Tenant helpers
def create_tenant(mongo, department_name, chairperson_email, password, trial_days):
    hashed = generate_password_hash(password)
    trial_end = datetime.utcnow() + timedelta(days=trial_days)
    return mongo.db.tenants.insert_one({
        'department_name': department_name,
        'chairperson_email': chairperson_email,
        'chairperson_password_hash': hashed,
        'trial_end_date': trial_end,
        'is_active': True,
        'created_at': datetime.utcnow()
    })

def get_tenant_by_email(mongo, email):
    return mongo.db.tenants.find_one({'chairperson_email': email})

def tenant_is_trial_valid(tenant_doc):
    return tenant_doc['trial_end_date'] > datetime.utcnow() and tenant_doc['is_active']

# Member helpers
def add_member(mongo, tenant_id, data):
    data['tenant_id'] = tenant_id
    data['join_date'] = datetime.utcnow()
    data['status'] = 'active'
    data.setdefault('role', 'member')   # default role
    last = mongo.db.members.find_one({'tenant_id': tenant_id}, sort=[('member_number', -1)])
    if last and 'member_number' in last:
        num = int(last['member_number'].replace('M', '')) + 1
    else:
        num = 1
    data['member_number'] = f'M{num:04d}'
    return mongo.db.members.insert_one(data)

def get_members_of_tenant(mongo, tenant_id):
    return list(mongo.db.members.find({'tenant_id': tenant_id}))

# Contribution helpers
def record_contribution(mongo, tenant_id, member_id, amount):
    return mongo.db.contributions.insert_one({
        'tenant_id': tenant_id,
        'member_id': member_id,
        'amount': amount,
        'date': datetime.utcnow(),
        'receipt_number': f'RCP{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
    })

def get_contributions_tenant(mongo, tenant_id):
    return list(mongo.db.contributions.find({'tenant_id': tenant_id}))

# Loan helpers (unchanged)
def create_loan(mongo, tenant_id, member_id, principal, interest_rate, duration_days):
    total = principal + (principal * interest_rate / 100)
    start = datetime.utcnow()
    due = start + timedelta(days=duration_days)
    return mongo.db.loans.insert_one({
        'tenant_id': tenant_id,
        'member_id': member_id,
        'principal': principal,
        'interest_rate': interest_rate,
        'total_repayable': total,
        'start_date': start,
        'due_date': due,
        'status': 'active',
        'repayments': []
    })

def get_loans_tenant(mongo, tenant_id):
    return list(mongo.db.loans.find({'tenant_id': tenant_id}))

def add_loan_repayment(mongo, loan_id, amount):
    mongo.db.loans.update_one(
        {'_id': loan_id},
        {'$push': {'repayments': {'amount': amount, 'date': datetime.utcnow()}}}
    )
    loan = mongo.db.loans.find_one({'_id': loan_id})
    if loan:
        total_repaid = sum(r['amount'] for r in loan['repayments'])
        if total_repaid >= loan['total_repayable']:
            mongo.db.loans.update_one({'_id': loan_id}, {'$set': {'status': 'repaid'}})

# Project helpers
def create_project(mongo, tenant_id, data):
    data['tenant_id'] = tenant_id
    data['status'] = 'proposed'
    data['contributions'] = []
    data['start_date'] = datetime.utcnow()
    return mongo.db.projects.insert_one(data)

def contribute_to_project(mongo, project_id, member_id, amount):
    mongo.db.projects.update_one(
        {'_id': project_id},
        {'$push': {'contributions': {'member_id': member_id, 'amount': amount, 'date': datetime.utcnow()}}}
    )

def get_projects_tenant(mongo, tenant_id):
    return list(mongo.db.projects.find({'tenant_id': tenant_id}))

# Notification helpers
def create_notification(mongo, tenant_id, message, sender='superadmin'):
    return mongo.db.notifications.insert_one({
        'tenant_id': tenant_id,
        'message': message,
        'sender': sender,
        'created_at': datetime.utcnow(),
        'read': False
    })

def get_notifications_for_tenant(mongo, tenant_id):
    return list(mongo.db.notifications.find({'tenant_id': tenant_id}).sort('created_at', -1))

# Tenant summary for monitoring
def get_tenant_summary(mongo, tenant_id):
    members = mongo.db.members.count_documents({'tenant_id': tenant_id})
    contrib = sum(c['amount'] for c in mongo.db.contributions.find({'tenant_id': tenant_id}))
    loans = mongo.db.loans.count_documents({'tenant_id': tenant_id, 'status': 'active'})
    projects = mongo.db.projects.count_documents({'tenant_id': tenant_id})
    return {'members': members, 'total_contributions': contrib, 'active_loans': loans, 'projects': projects}

def create_demo_tenant_if_not_exists(mongo):
    if mongo.db.tenants.count_documents({}) == 0:
        create_tenant(
            mongo,
            department_name="Mathematics Department",
            chairperson_email="mathchair@school.com",
            password="math123",
            trial_days=365
        )
        print("Demo tenant created: mathchair@school.com / math123")