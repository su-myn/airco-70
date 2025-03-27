from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# Company model
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    users = db.relationship('User', backref='company', lazy=True)

    def __repr__(self):
        return f"Company('{self.name}')"


# Role model
class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    # Role permissions
    can_view_complaints = db.Column(db.Boolean, default=False)
    can_manage_complaints = db.Column(db.Boolean, default=False)

    can_view_repairs = db.Column(db.Boolean, default=False)
    can_manage_repairs = db.Column(db.Boolean, default=False)

    can_view_replacements = db.Column(db.Boolean, default=False)
    can_manage_replacements = db.Column(db.Boolean, default=False)

    # Admin permissions
    is_admin = db.Column(db.Boolean, default=False)
    can_manage_users = db.Column(db.Boolean, default=False)

    users = db.relationship('User', backref='role', lazy=True)

    def __repr__(self):
        return f"Role('{self.name}')"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    # Foreign keys for company and role
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)

    # Relationships
    complaints = db.relationship('Complaint', backref='author', lazy=True)
    repairs = db.relationship('Repair', backref='author', lazy=True)
    replacements = db.relationship('Replacement', backref='author', lazy=True)

    @property
    def is_admin(self):
        return self.role.is_admin

    def has_permission(self, permission):
        return getattr(self.role, permission, False)

    def __repr__(self):
        return f"User('{self.name}', '{self.email}', '{self.company.name}', '{self.role.name}')"


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    remark = db.Column(db.String(200))
    unit = db.Column(db.String(20), nullable=False)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

    company = db.relationship('Company', backref='complaints')

    def __repr__(self):
        return f"Complaint('{self.item}', '{self.unit}')"


class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    remark = db.Column(db.String(200))
    unit = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

    company = db.relationship('Company', backref='repairs')

    def __repr__(self):
        return f"Repair('{self.item}', '{self.unit}', '{self.status}')"


class Replacement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    remark = db.Column(db.String(200))
    unit = db.Column(db.String(20), nullable=False)
    date_requested = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

    company = db.relationship('Company', backref='replacements')

    def __repr__(self):
        return f"Replacement('{self.item}', '{self.unit}', '{self.status}')"