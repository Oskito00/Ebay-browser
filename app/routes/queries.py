from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.models import LongTermItem, Query, db, Item, copy_item
from app.forms import QueryForm, DeleteForm  # Create this form if needed
from decimal import Decimal
from sqlalchemy import inspect, exists
from sqlalchemy.exc import OperationalError
from flask import current_app
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.utils.notifications import NotificationManager
from app.utils.text_helpers import filter_items_by_keywords, filter_items_by_price
from app.utils.query_helpers import update_user_usage, calculate_daily_runs

bp = Blueprint('queries', __name__, url_prefix='/queries')

@bp.route('/manage')
@login_required
def manage_queries():
    print("Current user:", current_user)
    queries = current_user.queries.all()
    print("Queries found:", queries)
    total_queries = len(queries)
    active_queries = len([query for query in queries if query.is_active])
    all_active = active_queries == total_queries
    delete_form = DeleteForm()
    return render_template('queries/manage.html', queries=queries, delete_form=delete_form, all_active=all_active)

@bp.route('/<string:query_id>', methods=['GET', 'POST'])
@login_required #TODO: Edit query button is not calling this function/ generally not working
def edit_query(query_id):
    query = Query.query.get_or_404(query_id)
    form = QueryForm(obj=query)  # Populate form from query object
    
    if form.validate_on_submit():
        form.populate_obj(query)  # Update query from form data
        db.session.commit()
        return redirect(url_for('queries.manage_queries'))
        
    return render_template('queries/edit.html', form=form, query=query)

@bp.route('/queries/<string:query_id>/delete', methods=['POST'])
@login_required
def delete_query(query_id):
    print("Delete query called")
    form = DeleteForm()
    print("Delete form:", form)
    if not form.validate_on_submit():
        flash('Invalid delete request', 'danger')
        return redirect(url_for('queries.manage_queries'))
    
    try:
        query = Query.query.get_or_404(query_id)
        
        # Authorization check
        if query.user != current_user:
            current_app.logger.warning(f"Unauthorized delete attempt by {current_user.id}")
            abort(403)

        # Calculate usage impact before deletion
        try:
            if query.is_active:
                update_user_usage(current_user, query, 'remove')
        except Exception as e:
            flash(f"Usage update failed: {str(e)}", 'warning')

        # --- Archive items before deletion ---
        archived_count = 0
        items_to_archive = query.search_items.all()
        print("Items to archive:", items_to_archive)
        if len(items_to_archive) > 0:
            try:
                print("Data type of query.search_items:", type(items_to_archive))
                print("Length of query.search_items:", len(items_to_archive))
                print("Archiving items...")
                print("query.search_items:", items_to_archive)
                archive_items(query)
                archived_count = len(items_to_archive)
                flash(f"Archived {archived_count} items", 'info')
                print(f"Archived {archived_count} items")
            except Exception as e:
                current_app.logger.error(f"Archive failed: {str(e)}")
                flash('Items could not be archived', 'warning')
                print(f"Archive failed: {str(e)}")

        # Delete query (cascade deletes items)
        db.session.delete(query)
        db.session.commit()
        
        print(f"Archived {archived_count} items")
        flash(f"Search deleted successfully. {archived_count} items archived.", 'success')
        current_app.logger.info(f"Deleted query {query_id}")

    except JobLookupError as e:
        current_app.logger.error(f"Job removal failed for query {query_id}: {str(e)}")
        flash('Search deleted but scheduler job not found', 'warning')
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.critical(f"Database error deleting query {query_id}: {str(e)}")
        flash('Error deleting search', 'danger')
    except Exception as e:
        current_app.logger.error(f"Unexpected error deleting query {query_id}: {str(e)}")
        flash('An unexpected error occurred', 'danger')
    
    return redirect(url_for('queries.manage_queries'))

@bp.route('/create_query', methods=['GET', 'POST'])
def create_query():
    print("Current user authenticated:", current_user.is_authenticated)
    form = QueryForm()
    if request.method == 'GET':
        form.check_interval.data = 5  # Default to 5 minutes
    print("Form data:", form.data)
    print("User ID:", current_user.id)
    if form.validate_on_submit():
        print("Form keywords:", form.keywords.data)
        print("Form check_interval:", form.check_interval.data)
        print("Submit button pressed:", 'submit' in request.form)
        print("Form submitted and validated")
        print("Required keywords:", form.required_keywords.data)
        print("Excluded keywords:", form.excluded_keywords.data)
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
                required_keywords=form.required_keywords.data,
                excluded_keywords=form.excluded_keywords.data,
                condition=form.condition.data,
                buying_options=form.buying_options.data,
                item_location=form.item_location.data,
                user_id=current_user.id,
                is_active=True
            )
            
            # Calculate potential usage
            try:
                if not update_user_usage(current_user, query, 'add'):
                    flash('This query would exceed your daily limit', 'danger')
                    return render_template('queries/create.html', form=form)
            except ValueError as e:
                flash(str(e), 'danger')
                return render_template('queries/create.html', form=form)

            # Proceed with creation if within limits
            query.needs_scheduling = True
            print("Query object:", query.__dict__)  # Before add
            db.session.add(query)
            db.session.commit()
            print("Query after commit:", query.id)  # Should have ID
            flash('Search query created!', 'success')

            try:
                count = load_historical_items(query)
                flash(f'Query created! Loaded {count} historical items', 'success')
            except Exception as e:
                flash(f'Query created, but failed to load history: {str(e)}', 'warning')

            inspector = inspect(db.engine)
            print("Tables in DB:", inspector.get_table_names())
            print("Query table exists:", 'queries' in inspector.get_table_names())
            try:
                test_query = Query.query.first()
                print("Test query from DB:", test_query)
            except OperationalError as e:
                print("DB Read Error:", str(e))
                        
            return redirect(url_for('queries.manage_queries'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Query creation failed: {str(e)}")
            flash('Error creating query: ' + str(e), 'danger')
    else:
        print("Form not validated. Errors:", form.errors)
    return render_template('queries/create.html', form=form) 

@bp.route('/queries/toggle_all', methods=['POST'])
@login_required
def toggle_all_queries():
    new_state = not current_user.queries.filter_by(is_active=True).count() > 0
    for query in current_user.queries:
        if query.is_active != new_state:
            operation = 'add' if new_state else 'remove'
            try:
                update_user_usage(current_user, query, operation)
                query.is_active = new_state
            except ValueError as e:
                db.session.rollback()
                flash(str(e), 'danger')
                return redirect(url_for('queries.manage_queries'))
    db.session.commit()
    return redirect(url_for('queries.manage_queries'))

@bp.route('/queries/<string:query_id>/toggle', methods=['POST'])
@login_required
def toggle_query(query_id):
    query = Query.query.get_or_404(query_id)
    if query.user != current_user:
        abort(403)
    
    operation = 'remove' if query.is_active else 'add'
    try:
        update_user_usage(current_user, query, operation)
        query.is_active = not query.is_active
        db.session.commit()
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('queries.manage_queries'))
    
    return redirect(url_for('queries.manage_queries'))


#*******************************
#HELPER FUNCTIONS
#*******************************

def archive_items(query):
    """Archive items to long-term storage"""
    for item in query.search_items.all():  # Changed from .items
        existing = LongTermItem.query.filter_by(
            ebay_id=item.ebay_id,
            keywords=query.keywords
        ).first()
        
        if existing:
            copy_item(item, existing)
            existing.recorded_at = datetime.now(timezone.utc)
        else:
            archived = LongTermItem()
            copy_item(item, archived)
            archived.keywords = query.keywords
            archived.recorded_at = datetime.now(timezone.utc)
            db.session.add(archived)
    
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Archive failed: {str(e)}")
        raise

def load_historical_items(query):
    print(f"\nLoading historical for query: {query.keywords}")
    historical = LongTermItem.query.filter_by(keywords=query.keywords).all()
    print(f"Found {len(historical)} historical items")
    
    # Convert to dicts for filtering
    hist_dicts = [
        {col.name: getattr(item, col.name) for col in LongTermItem.__table__.columns}
        for item in historical
    ]
    
    print("Running filter items")
    filtered_dicts = filter_items_by_keywords(
        hist_dicts,
        query.required_keywords,
        query.excluded_keywords,
    )

    filtered_dicts = filter_items_by_price(
        filtered_dicts,
        query.min_price,
        query.max_price
    )

    # Map back to original objects
    filtered_objs = [
        item for item in historical
        if any(d['ebay_id'] == item.ebay_id for d in filtered_dicts)
    ]

    print("Filtered objs:", filtered_objs)
    
    final_filtered = [
        item for item in filtered_objs
        if (item.marketplace == query.marketplace) or
           (item.location_country == query.item_location)   
            ]

    print("Final filtered:", final_filtered)
    
    # Check for existing items
    new_items = []
    print("Checking for existing items...")
    for hist in final_filtered:
        
        does_exist = db.session.query(
            exists().where(
                (Item.query_id == query.id) &
                (Item.ebay_id == hist.ebay_id)
            )
        ).scalar()
        
        if not does_exist:
            new_item = Item(query_id=query.id)
            copy_item(hist, new_item)
            new_items.append(new_item)
    
    if new_items:
        print("New items found, adding to DB")
        print("New items to add:", new_items)
        db.session.add_all(new_items)
        db.session.commit()
    
    print(f"\nPotential new items: {len(final_filtered)}")
    for idx, hist in enumerate(final_filtered, 1):
        does_exist = db.session.query(
            exists().where(
                (Item.query_id == query.id) &
                (Item.ebay_id == hist.ebay_id)
            )
        ).scalar()
        print(f"Item {idx}: ebay_id={hist.ebay_id}, exists={does_exist}")
    
    print(f"Final filtered count: {len(final_filtered)}")
    print(f"New items to add: {len(new_items)}")
    return len(new_items)