import os
import requests

def get_ebay_token():
    response = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        auth=(os.getenv('EBAY_CLIENT_ID'), os.getenv('EBAY_CLIENT_SECRET')),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'client_credentials',
            'scope': ' '.join([
                'https://api.ebay.com/oauth/api_scope',
                'https://api.ebay.com/oauth/api_scope/developer/analytics.read'
            ])
        }
    )
    response.raise_for_status()
    return response.json()['access_token']

if __name__ == "__main__":
    print("Your eBay token:", get_ebay_token())