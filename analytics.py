import requests
from datetime import datetime, timezone

from get_token import get_ebay_token



def get_rate_limits(access_token, api_name=None, api_context=None):
    """
    Get current rate limits for eBay APIs
    :param access_token: Valid OAuth token
    :param api_name: Optional API name filter (e.g., 'inventory')
    :param api_context: Optional API context filter (e.g., 'sell')
    :return: Parsed rate limit data
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {}
    if api_name:
        params['api_name'] = api_name
    if api_context:
        params['api_context'] = api_context
    
    response = requests.get(
        'https://api.ebay.com/developer/analytics/v1_beta/user_rate_limit/',
        headers=headers,
        params=params
    )
    response.raise_for_status()
    
    return _parse_rate_limits(response.json())

def _parse_rate_limits(data):
    """Parse rate limit response into structured format"""
    limits = []
    for api in data.get('rateLimits', []):
        for resource in api.get('resources', []):
            for limit in resource.get('limits', []):
                limits.append({
                    'api': f"{api['apiContext']}_{api['apiName']}",
                    'resource': resource['name'],
                    'window': limit['timeWindow'],
                    'max': limit['max'],
                    'remaining': limit['remaining'],
                    'reset': datetime.fromtimestamp(
                        int(limit['reset']), 
                        tz=timezone.utc
                    ) if 'reset' in limit else None
                })
    return limits




if __name__ == "__main__":
    limits = get_rate_limits(get_ebay_token())
    for limit in limits:
        print(f"{limit['api']} ({limit['window']}):")
        print(f"  Remaining: {limit['remaining']}/{limit['max']}")
        print(f"  Resets at: {limit['reset']}")