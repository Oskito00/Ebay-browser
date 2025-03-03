# Set your secret key. Remember to switch to your live secret key in production.
# See your keys here: https://dashboard.stripe.com/apikeys
import json
from flask import app, jsonify, request
import stripe


stripe.api_key = 'sk_test_51QybMQQ33R4TD00yn6UbEeC5mh1sEI57yjyz6QQHq0lMf1EBVnBrQWW6zsEhknq14aE5Y4v6HISBijmhW9EmPX3b000qJmkhB3'

@app.route('/webhook', methods=['POST'])
def webhook_received():
  webhook_secret = '{{STRIPE_WEBHOOK_SECRET}}'
  request_data = json.loads(request.data)

  if webhook_secret:
    # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
    signature = request.headers.get('stripe-signature')
    try:
      event = stripe.Webhook.construct_event(
          payload=request.data, sig_header=signature, secret=webhook_secret)
      data = event['data']
    except Exception as e:
      return e
    # Get the type of webhook event sent - used to check the status of PaymentIntents.
    event_type = event['type']
  else:
    data = request_data['data']
    event_type = request_data['type']
  data_object = data['object']

  if event_type == 'checkout.session.completed':
    # Payment is successful and the subscription is created.
    # You should provision the subscription and save the customer ID to your database.
    print(data)
  elif event_type == 'invoice.paid':
    # Continue to provision the subscription as payments continue to be made.
    # Store the status in your database and check when a user accesses your service.
    # This approach helps you avoid hitting rate limits.
    print(data)
  elif event_type == 'invoice.payment_failed':
    # The payment failed or the customer does not have a valid payment method.
    # The subscription becomes past_due. Notify your customer and send them to the
    # customer portal to update their payment information.
    print(data)
  else:
    print('Unhandled event type {}'.format(event_type))

  return jsonify({'status': 'success'})