# strava_pipeline.py
"""
Pipeline script to run all strava data processing steps in order.
"""
from trailtraining.data import strava as strava_processing
import pickle
import pandas as pd
from stravalib.client import Client
import os
import threading
from flask import Flask, request
import time
from trailtraining import config

app = Flask(__name__)
auth_code = {}
@app.route('/authorization')
def authorization():
    code = request.args.get('code')
    if code:
        auth_code['code'] = code
        return "Authorization successful! You can close this window."
    return "No code found.", 400

def run_flask():
    app.run(port=5000, debug=False, use_reloader=False)

def main():
    print("Fetching Strava data...")
    # --- Begin download_strava_data.py logic ---
    CLIENT_ID = int(os.environ.get('STRAVA_CLIENT_ID', config.STRAVA_ID))
    CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET', config.STRAVA_SECRET)
    pd.set_option("display.max_columns", 100)
    client = Client()
    MY_STRAVA_CLIENT_ID, MY_STRAVA_CLIENT_SECRET = CLIENT_ID, CLIENT_SECRET

    def authenticate_and_fetch_activities():
        # Start Flask server in background
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        url = client.authorization_url(
            client_id=MY_STRAVA_CLIENT_ID,
            redirect_uri='http://127.0.0.1:5000/authorization',
            scope=['read_all', 'profile:read_all', 'activity:read_all']
        )
        print("Please visit this URL to authorize the application:")
        print(url)

        # Wait for the code to be set by Flask
        while 'code' not in auth_code:
            time.sleep(1)
        code = auth_code['code']

        access_token = client.exchange_code_for_token(
            client_id=MY_STRAVA_CLIENT_ID,
            client_secret=MY_STRAVA_CLIENT_SECRET,
            code=code
        )
        with open('strava_access_token.pkl', 'wb') as f:
            pickle.dump(access_token, f)
        return access_token

    def load_access_token():
        with open('strava_access_token.pkl', 'rb') as f:
            return pickle.load(f)

    if not os.path.exists('strava_access_token.pkl'):
        access_token = authenticate_and_fetch_activities()
    else:
        access_token = load_access_token()
    client.access_token = access_token['access_token']
    try:
        athlete = client.get_athlete()
    except Exception as e:
        print(f"Access token invalid or expired. Re-authentication required. Error: {e}")
        access_token = authenticate_and_fetch_activities()
        client.access_token = access_token['access_token']
        athlete = client.get_athlete()
    print(f"Authenticated as {athlete.firstname} {athlete.lastname} (ID: {athlete.id})")
    activities = client.get_activities(limit=1000)
    cols = [
        'name', 'start_date_local', 'average_heartrate', 'max_heartrate', 'total_elevation_gain',
        'sport_type', 'moving_time', 'elev_low', 'elev_high', 'elapsed_time', 'distance'
    ]
    activities_array = []
    for activity in activities:
        activity_data = {'id': activity.id}
        for col in cols:
            activity_data[col] = getattr(activity, col, None)
        activities_array.append(activity_data)
    df = pd.DataFrame(activities_array)
    df['sport_type'] = df['sport_type'].astype(str)
    df['activity'] = df['sport_type'].apply(lambda x: x.split("'")[1] if isinstance(x, str) and "root=" in x else x)
    legacy_json_path = os.path.join(config.PROCESSING_DIRECTORY, "strava_activities.json")
    if os.path.exists(legacy_json_path):
        os.remove(legacy_json_path)
    # Ensure all columns are JSON-serializable
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)  # Convert objects to strings

    # Save to JSON
    try:
        json_path = os.path.join(config.PROCESSING_DIRECTORY, 'strava_activities.json')
        if os.path.exists(json_path):
            os.remove(json_path)
        df.to_json(json_path, orient='records', date_format='iso')
        print("Strava activities saved to JSON.")
    except Exception as e:
        print(f"Error saving JSON: {e}")
        # --- End download_strava_data.py logic ---
    print("Strava activities saved to JSON.")
    # --- End download_strava_data.py logic ---

if __name__ == "__main__":
    main()
