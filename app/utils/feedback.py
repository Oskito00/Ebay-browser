from datetime import datetime, timezone
from flask import current_app, request
from flask_login import current_user
from app.extensions import db

from app.models import Feedback


def save_cancellation_feedback():
    """Saves cancellation feedback to the database"""
    try:
        reasons = request.form.getlist('cancellation_reason')
        comment = request.form.get('cancellation_comment', '').strip()

        # Check if both are empty
        if not reasons and not comment:
            current_app.logger.info("Empty cancellation feedback skipped")
            return

        feedback = Feedback(
            user_id=current_user.id,
            feedback_type="cancellation",
            cancellation_reasons=",".join(reasons) if reasons else None,
            cancellation_comment=comment if comment else None,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(feedback)
        db.session.commit()
        current_app.logger.info(f"Saved cancellation feedback from user {current_user.id}")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to save feedback: {str(e)}")