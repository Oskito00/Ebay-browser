from flask import Flask, jsonify, request, render_template
from ebay_monitor import EbayMonitor
import os

app = Flask(__name__)
monitor = EbayMonitor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/queries', methods=['GET', 'POST', 'DELETE'])
def manage_queries():
    if request.method == 'POST':
        data = request.json
        query_id = monitor.add_query(
            keywords=data['keywords'],
            filters={
                'marketplace': data.get('marketplace', 'EBAY-GB'),
                'min_price': data.get('minPrice'),
                'max_price': data.get('maxPrice'),
                'required_keywords': data.get('requiredKeywords', '').split(','),
                'exclude_keywords': data.get('excludeKeywords', '').split(','),
                'condition': data.get('condition')
            }
        )
        return jsonify({'id': query_id})
    elif request.method == 'DELETE':
        monitor.remove_query(request.json['id'])
        return jsonify({'status': 'success'})
    return jsonify(monitor.get_queries())

@app.route('/control', methods=['POST'])
def control_monitor():
    action = request.json.get('action')
    if action == 'start':
        monitor.start()
    elif action == 'stop':
        monitor.stop()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run() 