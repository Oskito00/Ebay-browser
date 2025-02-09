from dotenv import load_dotenv
from pathlib import Path
import os

def pytest_configure():
    env_path = Path(__file__).parent / ".env"
    print(f"\nLoading .env from: {env_path}")
    load_dotenv(env_path)
    print("EBAY_ACCESS_TOKEN exists:", 'EBAY_ACCESS_TOKEN' in os.environ) 