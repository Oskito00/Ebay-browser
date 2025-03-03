

import os
import stripe
from app.models import User
from app.routes.subscription import create_customer


def test_create_customer(db_session):
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

    user = User(email='test@test.com')
    db_session.add(user)
    db_session.commit()
    create_customer(user)
    db_session.refresh(user)
    assert user.tier['tier'] == 'free'
    assert user.stripe_customer_id is not None