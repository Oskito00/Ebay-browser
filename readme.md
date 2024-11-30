# eBay Monitor

A web application that monitors eBay listings and sends Telegram notifications for new items.

## Setup

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your credentials:
```env
EBAY_CLIENT_ID=your_ebay_client_id
EBAY_CLIENT_SECRET=your_ebay_client_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

3. Run the application:
```bash
python app.py
```

## Features

- Monitor eBay listings for specific search terms
- Filter by price range and item condition
- Receive real-time Telegram notifications
- Web interface for easy configuration

## Usage

1. Open `http://localhost:5000` in your browser
2. Enter your search term
3. Set any desired filters
4. Click "Start Monitor"