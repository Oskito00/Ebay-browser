from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from app.models import Query, db

bp = Blueprint('queries', __name__, url_prefix='/queries')

@bp.route('/')
@login_required
def manage_queries():
    queries = current_user.queries.order_by(Query.created_at.desc()).all()
    return render_template('queries/manage.html', queries=queries)

@bp.route('/<int:query_id>', methods=['GET', 'POST'])
@login_required
def edit_query(query_id):
    query = Query.query.get_or_404(query_id)
    
    if request.method == 'POST':
        query.keywords = request.form['keywords']
        query.price_alert_threshold = float(request.form.get('threshold', 5.0))
        db.session.commit()
        return redirect(url_for('queries.manage_queries'))
    
    return render_template('queries/edit.html', query=query)

@bp.route('/<int:query_id>/delete', methods=['POST'])
@login_required
def delete_query(query_id):
    query = Query.query.get_or_404(query_id)
    db.session.delete(query)
    db.session.commit()
    return redirect(url_for('queries.manage_queries'))

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_query():
    if request.method == 'POST':
        query = Query(
            keywords=request.form['keywords'],
            price_alert_threshold=float(request.form['threshold']),
            user_id=current_user.id
        )
        db.session.add(query)
        db.session.commit()
        return redirect(url_for('queries.manage_queries'))
    return render_template('queries/create.html') 