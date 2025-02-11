from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.jobs.query_jobs import check_query
from app.models import Query, db
from app.forms import QueryForm, DeleteForm  # Create this form if needed
from decimal import Decimal
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from app import scheduler
from flask import current_app
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import JobLookupError

bp = Blueprint('queries', __name__, url_prefix='/queries')

@bp.route('/manage')
@login_required
def manage_queries():
    print("Current user:", current_user)
    queries = current_user.queries.all()
    print("Queries found:", queries)
    delete_form = DeleteForm()
    return render_template('queries/manage.html', queries=queries, delete_form=delete_form)

@bp.route('/<int:query_id>', methods=['GET', 'POST'])
@login_required #TODO: Edit query button is not calling this function/ generally not working
def edit_query(query_id):
    query = Query.query.get_or_404(query_id)
    form = QueryForm(obj=query)  # Populate form from query object
    
    if form.validate_on_submit():
        form.populate_obj(query)  # Update query from form data
        db.session.commit()
        return redirect(url_for('queries.manage_queries'))
        
    return render_template('queries/edit.html', form=form, query=query)

@bp.route('/<int:query_id>/delete', methods=['POST'])
@login_required
def delete_query(query_id):
    form = DeleteForm()
    if form.validate_on_submit():
        query = Query.query.get_or_404(query_id)
        db.session.delete(query)
        db.session.commit()
        flash('Search deleted', 'success')
        
        if current_app.config['ENABLE_SCHEDULER']:
            try:
                scheduler.remove_job(f'query_{query_id}')
            except JobLookupError:
                pass
    
    return redirect(url_for('queries.manage_queries'))

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_query():
    print("Current user authenticated:", current_user.is_authenticated)
    form = QueryForm()
    if request.method == 'GET':
        form.check_interval.data = 5  # Default to 1 hour
    print("Form data:", form.data)
    print("User ID:", current_user.id)
    if form.validate_on_submit():
        print("Form keywords:", form.keywords.data)
        print("Form check_interval:", form.check_interval.data)
        print("Submit button pressed:", 'submit' in request.form)
        print("Form submitted and validated")
        print("Form check_interval type:", type(form.check_interval.data))
        try:
            min_price = float(form.min_price.data) if form.min_price.data else None
            max_price = float(form.max_price.data) if form.max_price.data else None
            query = Query(
                marketplace=form.marketplace.data,
                keywords=form.keywords.data,
                check_interval=form.check_interval.data,
                min_price=Decimal(str(min_price)) if min_price else None,
                max_price=Decimal(str(max_price)) if max_price else None,
                item_location=form.item_location.data,
                user_id=current_user.id
            )
            print("Query object:", query.__dict__)  # Before add
            db.session.add(query)
            db.session.commit()
            print("Query after commit:", query.id)  # Should have ID
            flash('Search query created!', 'success')
            inspector = inspect(db.engine)
            print("Tables in DB:", inspector.get_table_names())
            print("Query table exists:", 'queries' in inspector.get_table_names())
            try:
                test_query = Query.query.first()
                print("Test query from DB:", test_query)
            except OperationalError as e:
                print("DB Read Error:", str(e))
            
            if current_app.config['ENABLE_SCHEDULER']:
                scheduler.add_job(
                    check_query,
                    'interval',
                    minutes=query.check_interval,
                    args=[query.id],
                    id=f'query_{query.id}'
                )
            
            return redirect(url_for('queries.manage_queries'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating query: ' + str(e), 'danger')
    else:
        print("Form not validated. Errors:", form.errors)
    return render_template('queries/create.html', form=form) 