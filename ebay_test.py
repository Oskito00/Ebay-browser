from ebaysdk.finding import Connection
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get and verify eBay App ID
EBAY_APP_ID = os.getenv('EBAY_APP_ID')
print(f"Loaded App ID: {EBAY_APP_ID}")  # This will help us verify the value

if not EBAY_APP_ID:
    raise ValueError("EBAY_APP_ID not found in environment variables. Check your .env file.")

def test_ebay_connection():
    try:
        # Create API connection
        api = Connection(appid=EBAY_APP_ID, config_file=None)
        
        # Make a test search
        response = api.execute('findItemsByKeywords', {
            'keywords': 'test',
        })
        
        print("Connection successful!")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    test_ebay_connection() 