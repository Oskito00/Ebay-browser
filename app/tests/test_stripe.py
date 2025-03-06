

import os
import time
from flask import current_app
import stripe
from app.models import User
from app.routes.subscription import schedule_cancellation, cancel_subscription_logic
from app.tests.conftest import db_session, app

def test_api_version():
    print(stripe.api_version)

def test_subscription_lifecycle(db_session):
    # Create customer
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    user = User(email='test@test.com')
    db_session.add(user)
    db_session.commit()


    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={'user_id': user.id}
        )
        user.stripe_customer_id = customer.id
        db_session.commit()

    # Create and attach payment method
    pm = stripe.PaymentMethod.create(
        type="card",
        card={"token": "tok_visa"}
    )

    stripe.PaymentMethod.attach(pm.id, customer=user.stripe_customer_id)
    stripe.Customer.modify(
        user.stripe_customer_id,
        invoice_settings={"default_payment_method": pm.id}
    )

    # Create test clock frozen at current time
    clock = stripe.test_helpers.TestClock.create(
    frozen_time=int(time.time()),
    name="Expiration Test")


    # Create subscription
    sub = stripe.Subscription.create(
        customer=user.stripe_customer_id,
        items=[{"price": "price_1Qyzw3Q33R4TD00yktty6j1I"}],
        payment_behavior='default_incomplete',  # Required for test clock
        cancel_at_period_end=False,
        test_clock=clock.id
    )

    cancel_subscription_logic(user)

    assert user.subscription_status == 'pending_cancellation'

    initial_end = sub.current_period_end
    # Advance clock to 1 second after period end
    stripe.test_helpers.TestClock.advance(
    clock.id,
    frozen_time=initial_end + 1)



    updated_sub = stripe.Subscription.retrieve(sub.id)
    assert updated_sub.cancel_at_period_end is True
    assert user.subscription_status == 'pending_cancellation'
