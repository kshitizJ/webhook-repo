from flask import Blueprint, jsonify, request
from datetime import datetime
from flask_cors import CORS
from dateutil import parser
from app.extensions import db_connect

webhook = Blueprint('Webhook', __name__, url_prefix='/webhook')
CORS(webhook)

events_collection = db_connect()

# Helper function to format date with suffix (e.g., 1st, 2nd, 3rd)
def format_date_suffix(day):
    if 11 <= day <= 13:
        return f'{day}th'
    if day % 10 == 1:
        return f'{day}st'
    if day % 10 == 2:
        return f'{day}nd'
    if day % 10 == 3:
        return f'{day}rd'
    return f'{day}th'

# Function to format the date
def format_timestamp(dt):
    day_suffix = format_date_suffix(dt.day)
    return dt.strftime(f"{day_suffix} %B %Y - %I:%M %p UTC")

@webhook.route('/receiver', methods=["POST"])
def receiver():
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.json

    if not payload:
        return jsonify({"error": "Invalid JSON payload"}), 400

    event_data = {}

    if event_type == 'push':
        # Parse and format timestamp
        raw_timestamp = parser.isoparse(payload['head_commit']['timestamp'])
        formatted_timestamp = format_timestamp(raw_timestamp)
        event_data = {
            'request_id': payload['head_commit']['id'],  # Commit hash
            'author': payload['pusher']['name'],
            'action': 'PUSH',
            'from_branch': payload['ref'].split('/')[-1],  # Branch name
            'to_branch': payload['ref'].split('/')[-1],    # Pushes happen to the same branch
            'timestamp': formatted_timestamp
        }

    elif event_type == 'pull_request':
        # Pull Request Created
        if payload['action'] == 'opened':
            raw_timestamp = parser.isoparse(payload['pull_request']['created_at'])
            formatted_timestamp = format_timestamp(raw_timestamp)
            event_data = {
                'request_id': str(payload['pull_request']['id']),  # PR ID
                'author': payload['pull_request']['user']['login'],
                'action': 'PULL_REQUEST',
                'from_branch': payload['pull_request']['head']['ref'],
                'to_branch': payload['pull_request']['base']['ref'],
                'timestamp': formatted_timestamp
            }
        # Pull Request Merged (This is the actual 'merge' event)
        elif payload['action'] == 'closed' and payload['pull_request']['merged']:
            formatted_timestamp = format_timestamp(datetime.now())  # Current UTC time
            event_data = {
                'request_id': str(payload['pull_request']['id']),  # PR ID
                'author': payload['pull_request']['user']['login'],
                'action': 'MERGE',
                'from_branch': payload['pull_request']['head']['ref'],
                'to_branch': payload['pull_request']['base']['ref'],
                'timestamp': formatted_timestamp
            }

    else:
        return jsonify({'message': 'Unsupported event type'}), 400

    # Store event in MongoDB
    events_collection.insert_one(event_data)
    return jsonify({'message': 'Event received'}), 200

# API to fetch latest events
@webhook.route('/events', methods=['GET'])
def get_events():
    events = list(events_collection.find().sort('timestamp', -1).limit(10))
    for event in events:
        event['_id'] = str(event['_id'])  # Convert ObjectId to string for JSON serialization
    return jsonify(events)
