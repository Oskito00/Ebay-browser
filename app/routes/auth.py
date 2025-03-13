from flask import Blueprint, app, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from app.models import User
from app.forms import LoginForm, RegistrationForm
from app import db

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    print("User pressed login button")
    form = LoginForm()
    print("Form data:", form.data)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        print("User found:", user)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('auth.login'))
        if not user.check_password(form.password.data):
            flash('Invalid password', 'danger')
            return redirect(url_for('auth.login'))
        login_user(user)
        print(f"User logged in: {user.email}")
        flash('Logged in successfully!', 'success')
        return redirect(url_for('queries.manage_queries'))
        flash('Invalid email or password', 'danger')
    return render_template('auth/login.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if email exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            print("User already exists")
            flash('This email is already registered. Please use a different email.', 'danger')
            return render_template('auth/register.html', form=form)
        
        try:
            user = User(email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            print(f"User logged in: {user.email}")
            flash('Registration successful!', 'success')
            return redirect(url_for('queries.manage_queries'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'danger')
            app.logger.error(f"Registration error: {str(e)}")
    
    return render_template('auth/register.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index')) 