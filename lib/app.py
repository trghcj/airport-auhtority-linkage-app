# app.py
import csv
import io
from datetime import datetime, timedelta

import requests
from flask import Flask, jsonify
from flask_cors import CORS

# --- Configuration ---
# Define the Google Sheet CSV URL from your Flutter app
GOOGLE_SHEET_CSV_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQtLmQY6Ow4enOWKqV_RkHTVkW9pTOV_6h73FrMNZ6lUsp08UwSGQi0n9WDLTK0Rw/pub?gid=1055316290&single=true&output=csv'

# --- Flask App Initialization ---
app = Flask(__name__)
# Enable CORS to allow requests from your Flutter web app
CORS(app)

# --- Helper Functions for Data Processing ---

def _gmt_to_ist(date_str, time_val):
    """Converts a GMT date and time string to an IST datetime object."""
    try:
        # Parse date (assuming DD/MM/YYYY format)
        date_parts = date_str.split('/')
        if len(date_parts) != 3:
            return None
        
        day, month, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])

        # Parse time (assuming HHMM format)
        time_str = str(time_val).zfill(4)
        hours, minutes = int(time_str[:2]), int(time_str[2:])
        
        # Create a GMT datetime object and convert to IST
        gmt_datetime = datetime(year, month, day, hours, minutes)
        ist_datetime = gmt_datetime + timedelta(hours=5, minutes=30)
        
        return ist_datetime
    except (ValueError, IndexError) as e:
        print(f"Error converting GMT to IST for date '{date_str}' and time '{time_val}': {e}")
        return None

def _get_air_status(hours):
    """Determines the status and color based on total air hours."""
    if hours is None or hours == 0:
        return 'Missing', '#808080'  # Grey
    elif hours < 10:
        return 'Red (<10)', '#F44336'  # Red
    elif 10 <= hours <= 14:
        return 'Yellow (10–14)', '#FF9800'  # Orange
    else:
        return 'Green (>14)', '#4CAF50'  # Green

def _fetch_and_process_data():
    """
    Fetches CSV data from Google Sheets and processes it for flights,
    billing, and airtime analysis.
    """
    try:
        response = requests.get(GOOGLE_SHEET_CSV_URL)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return None, None, None

    # Use StringIO to treat the string response body as a file
    csv_file = io.StringIO(response.text)
    
    # Read the CSV data, skipping the header row
    reader = csv.reader(csv_file)
    header = next(reader, None)
    if not header:
        return [], [], []

    data_rows = list(reader)

    flights = []
    billing_records = []
    
    # --- Process each row for flight and billing info ---
    for i, row in enumerate(data_rows):
        # Pad the row with None if it's shorter than the header
        while len(row) < len(header):
            row.append(None)
        
        # --- Flight Processing ---
        try:
            travel_linkage = row[5].strip() if row[5] else ''
            is_linkage_missing = not travel_linkage or travel_linkage.lower() == 'n/a'
            
            # Safely get date/time values, defaulting to None if columns don't exist
            arr_date, arr_gmt = (row[9], row[10]) if len(row) > 10 else (None, None)
            dep_date, dep_gmt = (row[11], row[12]) if len(row) > 12 else (None, None)

            arrival_ist = _gmt_to_ist(arr_date, arr_gmt) if arr_date and arr_gmt else None
            departure_ist = _gmt_to_ist(dep_date, dep_gmt) if dep_date and dep_gmt else None

            air_hours = 0.0
            if arrival_ist and departure_ist:
                # Calculate airtime in hours
                time_difference = departure_ist - arrival_ist
                air_hours = time_difference.total_seconds() / 3600.0

            flights.append({
                'flightNumber': row[0],
                'departureCity': row[1],
                'arrivalCity': row[2],
                'departureTime': row[3],
                'arrivalTime': row[4],
                'travelLinkage': travel_linkage,
                'isLinkageMissing': is_linkage_missing,
                'regNo': row[6].strip() if row[6] else '',
                'arrFlightNo': row[7] if len(row) > 7 else '',
                'depFlightNo': row[8] if len(row) > 8 else '',
                'arrivalIST': arrival_ist.isoformat() if arrival_ist else None,
                'departureIST': departure_ist.isoformat() if departure_ist else None,
                'airHours': air_hours,
            })
        except Exception as e:
            print(f"Error processing flight data in row {i+1}: {e}")

        # --- Billing Processing ---
        try:
            if len(row) >= 10 and row[6] and row[7]:
                total_bill = float(row[6])
                amount_paid = float(row[7])
                due_date_str = row[8]
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
                
                amount_remaining = total_bill - amount_paid
                is_overdue = due_date and datetime.now() > due_date and amount_remaining > 0

                billing_records.append({
                    'flightNumber': row[0],
                    'totalBill': total_bill,
                    'amountPaid': amount_paid,
                    'dueDate': due_date.isoformat() if due_date else None,
                    'paymentStatusRaw': row[9],
                    'isOverdue': is_overdue,
                    'amountRemaining': amount_remaining,
                })
        except (ValueError, IndexError) as e:
            print(f"Skipping billing processing for row {i+1} due to missing/invalid data: {e}")


    # --- Daily Airtime Analysis ---
    grouped_flights = {}
    for flight in flights:
        if flight['arrivalIST'] and flight['regNo']:
            # Group by date and registration number
            arrival_date = datetime.fromisoformat(flight['arrivalIST']).date()
            date_key = arrival_date.isoformat()
            reg_no = flight['regNo']

            if date_key not in grouped_flights:
                grouped_flights[date_key] = {}
            if reg_no not in grouped_flights[date_key]:
                grouped_flights[date_key][reg_no] = 0.0
            
            grouped_flights[date_key][reg_no] += flight['airHours']

    daily_airtime_list = []
    for date_str, reg_groups in grouped_flights.items():
        for reg_no, total_hours in reg_groups.items():
            status, status_color_hex = _get_air_status(total_hours)
            daily_airtime_list.append({
                'flightDate': date_str,
                'regNo': reg_no,
                'totalAirHours': total_hours,
                'status': status,
                # Store color as a hex string for Flutter to parse
                'statusColor': status_color_hex,
            })
            
    # Sort by date (desc) and registration number (asc)
    daily_airtime_list.sort(key=lambda x: (x['flightDate'], x['regNo']), reverse=True)

    return flights, billing_records, daily_airtime_list

# --- API Endpoint ---
@app.route('/api/data')
def get_data():
    """
    Main API endpoint to serve all processed data as a single JSON object.
    """
    flights, billing, daily_airtime = _fetch_and_process_data()
    
    if flights is None:
        return jsonify({"error": "Failed to fetch or process data from the source."}), 500
        
    return jsonify({
        'flights': flights,
        'billing': billing,
        'dailyAirtime': daily_airtime,
    })

# --- Main Execution ---
if __name__ == '__main__':
    # Run the Flask app on host 0.0.0.0 to be accessible from your local network
    app.run(host='0.0.0.0', port=5000, debug=True)
