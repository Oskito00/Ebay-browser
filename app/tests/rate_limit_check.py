import requests
import os

def get_rate_limits():
    # Get token first
    token_response = requests.post(
        'https://api.ebay.com/identity/v1/oauth2/token',
        auth=(os.getenv('EBAY_CLIENT_ID'), os.getenv('EBAY_CLIENT_SECRET')),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'client_credentials',
            'scope': 'https://api.ebay.com/oauth/api_scope'
        }
    )
    token_response.raise_for_status()
    token = token_response.json()['access_token']
    
    # Check rate limits
    limits_response = requests.get(
        'https://api.ebay.com/developer/analytics/v1_beta/rate_limit',
        headers={'Authorization': f'Bearer {token}'}
    )
    limits_response.raise_for_status()
    return limits_response.json()

def test_rate_limits():
    # ... get limits ...
    try:
        limits = get_rate_limits()
        for api in limits['rateLimits']:
            if api['apiContext'].lower() == 'buy' and api['apiName'].lower() == 'browse':
                print("\nBrowse API Limits:")
                for resource in api['resources']:
                    if resource['name'] == 'buy.browse':
                        rate = resource['rates'][0]
                        print(f"Daily Used: {rate['limit'] - rate['remaining']}/{rate['limit']}")
                        print(f"Remaining: {rate['remaining']}")
                        print(f"Reset Time: {rate['reset']}")
                        break
                break
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    try:
        test_rate_limits()
    except Exception as e:
        print(f"Error: {str(e)}")