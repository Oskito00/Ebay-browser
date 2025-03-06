from http.client import HTTPResponse
from flask import Blueprint, current_app, jsonify, request
from flask_wtf.csrf import CSRFProtect
import stripe

from app.stripe.stripe_fulfillment import handle_invoice_paid, handle_invoice_payment_failed, handle_new_subscription, handle_subscription_deleted, handle_subscription_updated


csrf = CSRFProtect()

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.before_request
def configure_stripe():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

@webhook_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def my_webhook_view():
  payload = request.data
  sig_header = request.headers.get('Stripe-Signature')
  event = None

  try:
    event = stripe.Webhook.construct_event(
      payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
    )
  except ValueError as e:
    # Invalid payload
    return HTTPResponse(status=400)
  except stripe.error.SignatureVerificationError as e:
    # Invalid signature
    return HTTPResponse(status=400)
  
  handle_event(event)

  return jsonify({'status': 'success'}), 200

def handle_event(event):
    handler_map = {
    # Core Subscription Events
    # 'checkout.session.completed': handle_checkout_completed,
    'customer.subscription.created': handle_new_subscription,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    
    # Payment & Billing
    'invoice.paid': handle_invoice_paid,
    'invoice.payment_failed': handle_invoice_payment_failed,
    
    # Customer Management
    # 'customer.updated': handle_customer_updated,
    # 'customer.deleted': handle_customer_deleted,
}
    
    handler = handler_map.get(event['type'])
    if handler:
        handler(event)
    else:
        print(f"No handler for {event['type']}")