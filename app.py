from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import os
import pytz
from datetime import datetime
from models import db, User, Complaint, Repair, Replacement, Company, Role

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///propertyhub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
db.init_app(app)


# Add template filter for Malaysia timezone
@app.template_filter('malaysia_time')
def malaysia_time_filter(utc_dt):
    """Convert UTC datetime to Malaysia timezone"""
    if utc_dt is None:
        return ""
    malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    malaysia_time = utc_dt.astimezone(malaysia_tz)
    return malaysia_time.strftime('%b %d, %Y, %I:%M %p')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Permission-based decorators
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.has_permission(permission):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


# Specific permission decorators
def complaints_view_required(f):
    return permission_required('can_view_complaints')(f)


def complaints_manage_required(f):
    return permission_required('can_manage_complaints')(f)


def repairs_view_required(f):
    return permission_required('can_view_repairs')(f)


def repairs_manage_required(f):
    return permission_required('can_manage_repairs')(f)


def replacements_view_required(f):
    return permission_required('can_view_replacements')(f)


def replacements_manage_required(f):
    return permission_required('can_manage_replacements')(f)


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('You have been logged in successfully', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login failed. Please check your email and password', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check if password and confirm_password match
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already registered. Please use a different email or login', 'danger')
            return redirect(url_for('register'))

        # Get default company and role
        default_company = Company.query.first()
        if not default_company:
            default_company = Company(name="Default Company")
            db.session.add(default_company)
            db.session.commit()

        # Find a non-admin role
        user_role = Role.query.filter_by(name="Manager").first()
        if not user_role:
            user_role = Role.query.filter(Role.is_admin.is_(False)).first()
        if not user_role:
            # If no non-admin role exists, create a basic user role
            user_role = Role(name="User",
                             can_view_complaints=True,
                             can_view_repairs=True,
                             can_view_replacements=True)
            db.session.add(user_role)
            db.session.commit()

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            company_id=default_company.id,
            role_id=user_role.id
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! You can now sign in', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/dashboard')
@login_required
def dashboard():
    # Filter records to only show those belonging to the user's company
    # but respect the role permissions
    user_company_id = current_user.company_id

    complaints = []
    repairs = []
    replacements = []

    if current_user.has_permission('can_view_complaints'):
        complaints = Complaint.query.filter_by(company_id=user_company_id).all()

    if current_user.has_permission('can_view_repairs'):
        repairs = Repair.query.filter_by(company_id=user_company_id).all()

    if current_user.has_permission('can_view_replacements'):
        replacements = Replacement.query.filter_by(company_id=user_company_id).all()

    return render_template('dashboard.html', complaints=complaints, repairs=repairs, replacements=replacements)


# Complaint routes
@app.route('/add_complaint', methods=['POST'])
@login_required
@permission_required('can_manage_complaints')
def add_complaint():
    item = request.form['item']
    remark = request.form['remark']
    unit = request.form['unit']

    new_complaint = Complaint(
        item=item,
        remark=remark,
        unit=unit,
        author=current_user,
        company_id=current_user.company_id
    )
    db.session.add(new_complaint)
    db.session.commit()

    flash('Complaint added successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update_complaint/<int:id>', methods=['POST'])
@login_required
@permission_required('can_manage_complaints')
def update_complaint(id):
    complaint = Complaint.query.get_or_404(id)

    # Ensure the current user's company matches the complaint's company
    if complaint.company_id != current_user.company_id:
        flash('You are not authorized to update this complaint', 'danger')
        return redirect(url_for('dashboard'))

    complaint.item = request.form['item']
    complaint.remark = request.form['remark']
    complaint.unit = request.form['unit']

    db.session.commit()
    flash('Complaint updated successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_complaint/<int:id>')
@login_required
@permission_required('can_manage_complaints')
def delete_complaint(id):
    complaint = Complaint.query.get_or_404(id)

    # Ensure the current user's company matches the complaint's company
    if complaint.company_id != current_user.company_id:
        flash('You are not authorized to delete this complaint', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(complaint)
    db.session.commit()

    flash('Complaint deleted successfully', 'success')
    return redirect(url_for('dashboard'))


# Repair routes
@app.route('/add_repair', methods=['POST'])
@login_required
@permission_required('can_manage_repairs')
def add_repair():
    item = request.form['item']
    remark = request.form['remark']
    unit = request.form['unit']
    status = request.form['status']

    new_repair = Repair(
        item=item,
        remark=remark,
        unit=unit,
        status=status,
        author=current_user,
        company_id=current_user.company_id
    )
    db.session.add(new_repair)
    db.session.commit()

    flash('Repair request added successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update_repair/<int:id>', methods=['POST'])
@login_required
@permission_required('can_manage_repairs')
def update_repair(id):
    repair = Repair.query.get_or_404(id)

    # Ensure the current user's company matches the repair's company
    if repair.company_id != current_user.company_id:
        flash('You are not authorized to update this repair request', 'danger')
        return redirect(url_for('dashboard'))

    repair.item = request.form['item']
    repair.remark = request.form['remark']
    repair.unit = request.form['unit']
    repair.status = request.form['status']

    db.session.commit()
    flash('Repair request updated successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_repair/<int:id>')
@login_required
@permission_required('can_manage_repairs')
def delete_repair(id):
    repair = Repair.query.get_or_404(id)

    # Ensure the current user's company matches the repair's company
    if repair.company_id != current_user.company_id:
        flash('You are not authorized to delete this repair request', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(repair)
    db.session.commit()

    flash('Repair request deleted successfully', 'success')
    return redirect(url_for('dashboard'))


# Replacement routes
@app.route('/add_replacement', methods=['POST'])
@login_required
@permission_required('can_manage_replacements')
def add_replacement():
    item = request.form['item']
    remark = request.form['remark']
    unit = request.form['unit']
    status = request.form['status']

    new_replacement = Replacement(
        item=item,
        remark=remark,
        unit=unit,
        status=status,
        author=current_user,
        company_id=current_user.company_id
    )
    db.session.add(new_replacement)
    db.session.commit()

    flash('Replacement request added successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/update_replacement/<int:id>', methods=['POST'])
@login_required
@permission_required('can_manage_replacements')
def update_replacement(id):
    replacement = Replacement.query.get_or_404(id)

    # Ensure the current user's company matches the replacement's company
    if replacement.company_id != current_user.company_id:
        flash('You are not authorized to update this replacement request', 'danger')
        return redirect(url_for('dashboard'))

    replacement.item = request.form['item']
    replacement.remark = request.form['remark']
    replacement.unit = request.form['unit']
    replacement.status = request.form['status']

    db.session.commit()
    flash('Replacement request updated successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_replacement/<int:id>')
@login_required
@permission_required('can_manage_replacements')
def delete_replacement(id):
    replacement = Replacement.query.get_or_404(id)

    # Ensure the current user's company matches the replacement's company
    if replacement.company_id != current_user.company_id:
        flash('You are not authorized to delete this replacement request', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(replacement)
    db.session.commit()

    flash('Replacement request deleted successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


# Admin routes
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    companies = Company.query.all()
    roles = Role.query.all()
    complaints = Complaint.query.all()
    repairs = Repair.query.all()
    replacements = Replacement.query.all()

    # Get count of each type by company
    company_stats = []
    for company in companies:
        company_users = User.query.filter_by(company_id=company.id).count()
        company_complaints = Complaint.query.filter_by(company_id=company.id).count()
        company_repairs = Repair.query.filter_by(company_id=company.id).count()
        company_replacements = Replacement.query.filter_by(company_id=company.id).count()

        company_stats.append({
            'name': company.name,
            'users': company_users,
            'complaints': company_complaints,
            'repairs': company_repairs,
            'replacements': company_replacements
        })

    return render_template('admin/dashboard.html',
                           users=users,
                           companies=companies,
                           roles=roles,
                           complaints=complaints,
                           repairs=repairs,
                           replacements=replacements,
                           company_stats=company_stats)


# User management routes
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_user():
    # Get all companies and roles for the form
    companies = Company.query.all()
    roles = Role.query.all()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        company_id = request.form['company_id']
        role_id = request.form['role_id']

        # Check if user already exists
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already registered', 'danger')
            return redirect(url_for('admin_add_user'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            company_id=company_id,
            role_id=role_id
        )
        db.session.add(new_user)
        db.session.commit()

        flash('User added successfully', 'success')
        return redirect(url_for('admin_users'))

    return render_template('admin/add_user.html', companies=companies, roles=roles)


@app.route('/admin/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(id):
    user = User.query.get_or_404(id)
    companies = Company.query.all()
    roles = Role.query.all()

    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.company_id = request.form['company_id']
        user.role_id = request.form['role_id']

        # Only update password if provided
        if request.form['password'].strip():
            user.password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('admin_users'))

    return render_template('admin/edit_user.html', user=user, companies=companies, roles=roles)


@app.route('/admin/delete_user/<int:id>')
@login_required
@admin_required
def admin_delete_user(id):
    if id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('admin_users'))

    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()

    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_users'))


# Company routes
@app.route('/admin/companies')
@login_required
@admin_required
def admin_companies():
    companies = Company.query.all()
    return render_template('admin/companies.html', companies=companies)


@app.route('/admin/add_company', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_company():
    if request.method == 'POST':
        name = request.form['name']

        # Check if company already exists
        company = Company.query.filter_by(name=name).first()
        if company:
            flash('Company already exists', 'danger')
            return redirect(url_for('admin_add_company'))

        new_company = Company(name=name)
        db.session.add(new_company)
        db.session.commit()

        flash('Company added successfully', 'success')
        return redirect(url_for('admin_companies'))

    return render_template('admin/add_company.html')


@app.route('/admin/edit_company/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_company(id):
    company = Company.query.get_or_404(id)

    if request.method == 'POST':
        company.name = request.form['name']
        db.session.commit()
        flash('Company updated successfully', 'success')
        return redirect(url_for('admin_companies'))

    return render_template('admin/edit_company.html', company=company)


@app.route('/admin/delete_company/<int:id>')
@login_required
@admin_required
def admin_delete_company(id):
    company = Company.query.get_or_404(id)

    # Check if company has users
    if company.users:
        flash('Cannot delete company with existing users', 'danger')
        return redirect(url_for('admin_companies'))

    db.session.delete(company)
    db.session.commit()

    flash('Company deleted successfully', 'success')
    return redirect(url_for('admin_companies'))


# Role routes
@app.route('/admin/roles')
@login_required
@admin_required
def admin_roles():
    roles = Role.query.all()
    return render_template('admin/roles.html', roles=roles)


@app.route('/admin/add_role', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_role():
    if request.method == 'POST':
        name = request.form['name']

        # Check if role already exists
        role = Role.query.filter_by(name=name).first()
        if role:
            flash('Role already exists', 'danger')
            return redirect(url_for('admin_add_role'))

        # Create new role with permissions
        new_role = Role(
            name=name,
            can_view_complaints='can_view_complaints' in request.form,
            can_manage_complaints='can_manage_complaints' in request.form,
            can_view_repairs='can_view_repairs' in request.form,
            can_manage_repairs='can_manage_repairs' in request.form,
            can_view_replacements='can_view_replacements' in request.form,
            can_manage_replacements='can_manage_replacements' in request.form,
            is_admin='is_admin' in request.form,
            can_manage_users='can_manage_users' in request.form
        )

        db.session.add(new_role)
        db.session.commit()

        flash('Role added successfully', 'success')
        return redirect(url_for('admin_roles'))

    return render_template('admin/add_role.html')


@app.route('/admin/edit_role/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_role(id):
    role = Role.query.get_or_404(id)

    if request.method == 'POST':
        role.name = request.form['name']

        # Update permissions
        role.can_view_complaints = 'can_view_complaints' in request.form
        role.can_manage_complaints = 'can_manage_complaints' in request.form
        role.can_view_repairs = 'can_view_repairs' in request.form
        role.can_manage_repairs = 'can_manage_repairs' in request.form
        role.can_view_replacements = 'can_view_replacements' in request.form
        role.can_manage_replacements = 'can_manage_replacements' in request.form
        role.is_admin = 'is_admin' in request.form
        role.can_manage_users = 'can_manage_users' in request.form

        db.session.commit()
        flash('Role updated successfully', 'success')
        return redirect(url_for('admin_roles'))

    return render_template('admin/edit_role.html', role=role)


@app.route('/admin/delete_role/<int:id>')
@login_required
@admin_required
def admin_delete_role(id):
    role = Role.query.get_or_404(id)

    # Check if role has users
    if role.users:
        flash('Cannot delete role with existing users', 'danger')
        return redirect(url_for('admin_roles'))

    db.session.delete(role)
    db.session.commit()

    flash('Role deleted successfully', 'success')
    return redirect(url_for('admin_roles'))


@app.route('/admin/complaints')
@login_required
@admin_required
def admin_complaints():
    complaints = Complaint.query.all()
    return render_template('admin/complaints.html', complaints=complaints)


@app.route('/admin/repairs')
@login_required
@admin_required
def admin_repairs():
    repairs = Repair.query.all()
    return render_template('admin/repairs.html', repairs=repairs)


@app.route('/admin/replacements')
@login_required
@admin_required
def admin_replacements():
    replacements = Replacement.query.all()
    return render_template('admin/replacements.html', replacements=replacements)


# Function to create default roles and a default company
def create_default_data():
    # Check if default company exists
    default_company = Company.query.filter_by(name="Default Company").first()
    if not default_company:
        default_company = Company(name="Default Company")
        db.session.add(default_company)
        db.session.commit()
        print("Default company created")

    # Create default roles if they don't exist
    roles = {
        "Admin": {
            "can_view_complaints": True,
            "can_manage_complaints": True,
            "can_view_repairs": True,
            "can_manage_repairs": True,
            "can_view_replacements": True,
            "can_manage_replacements": True,
            "is_admin": True,
            "can_manage_users": True
        },
        "Manager": {
            "can_view_complaints": True,
            "can_manage_complaints": True,
            "can_view_repairs": True,
            "can_manage_repairs": True,
            "can_view_replacements": True,
            "can_manage_replacements": True,
            "is_admin": False,
            "can_manage_users": False
        },
        "Technician": {
            "can_view_complaints": True,
            "can_manage_complaints": False,
            "can_view_repairs": True,
            "can_manage_repairs": True,
            "can_view_replacements": False,
            "can_manage_replacements": False,
            "is_admin": False,
            "can_manage_users": False
        },
        "Cleaner": {
            "can_view_complaints": False,
            "can_manage_complaints": False,
            "can_view_repairs": False,
            "can_manage_repairs": False,
            "can_view_replacements": True,
            "can_manage_replacements": True,
            "is_admin": False,
            "can_manage_users": False
        }
    }

    for role_name, permissions in roles.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, **permissions)
            db.session.add(role)
            db.session.commit()
            print(f"Role '{role_name}' created")

    # Create admin user if no admin exists
    admin_role = Role.query.filter_by(name="Admin").first()
    admin = User.query.filter_by(is_admin=True).first()

    if not admin and admin_role:
        password = 'admin123'  # Default password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        admin = User(
            name='Admin',
            email='admin@example.com',
            password=hashed_password,
            role_id=admin_role.id,
            company_id=default_company.id
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin user created with email: admin@example.com and password: admin123')


# Create the database tables
with app.app_context():
    db.create_all()
    create_default_data()

if __name__ == '__main__':
    app.run(debug=True)