from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import Query, db
from app.forms import QueryForm, DeleteForm  # Create this form if needed

bp = Blueprint('queries', __name__, url_prefix='/queries')

@bp.route('/manage')
@login_required
def manage_queries():
    queries = current_user.queries.order_by(Query.created_at.desc()).all()
    delete_form = DeleteForm()
    return render_template('queries/manage.html', queries=queries, delete_form=delete_form)

@bp.route('/<int:query_id>', methods=['GET', 'POST'])
@login_required
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
    return redirect(url_for('queries.manage_queries'))

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_query():
    form = QueryForm()
    if form.validate_on_submit():
        filters = {
            'min_price': form.min_price.data,
            'max_price': form.max_price.data,
            'condition': form.condition.data,
            'check_interval': form.check_interval.data * 60  # Convert to seconds
        }
        
        query = Query(
            keywords=form.keywords.data,
            filters=filters,
            user_id=current_user.id
        )
        
        db.session.add(query)
        db.session.commit()
        return redirect(url_for('queries.manage_queries'))
    
    return render_template('queries/create.html', form=form) 