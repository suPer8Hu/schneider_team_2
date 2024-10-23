import pandas as pd
import time
from flask import Flask, request, render_template
import logging
from datetime import datetime

# Initialize the Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

# Load CSV files
load_posting_path = '/Users/harshsahay/Desktop/Schneider_App/load_posting.csv'
load_stop_path = '/Users/harshsahay/Desktop/Schneider_App/load_stop.csvv'

try:
    load_posting = pd.read_csv(load_posting_path)
    load_stop = pd.read_csv(load_stop_path)
    logging.info("CSV files loaded successfully.")
except Exception as e:
    logging.error(f"Error loading CSV files: {e}")

# Data Cleaning
important_columns_posting = ['LOAD_ID', 'POSTING_STATUS', 'TRANSPORT_MODE', 'IS_HAZARDOUS', 'IS_HIGH_VALUE', 'DIVISION']
important_columns_stop = ['LOAD_ID', 'CITY', 'STATE', 'APPOINTMENT_FROM', 'APPOINTMENT_TO', 'STOP_SEQUENCE', 'STOP_TYPE']

try:
    load_posting.dropna(subset=important_columns_posting, inplace=True)
    load_stop.dropna(subset=important_columns_stop, inplace=True)
    load_posting.fillna('', inplace=True)
    load_stop.fillna('', inplace=True)
    logging.info("Data cleaning completed successfully.")
except Exception as e:
    logging.error(f"Error during data cleaning: {e}")

# Date validation function
def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def enhanced_search(trailer_type=None, origin_city=None, origin_state=None, destination_city=None, destination_state=None, pickup_date=None, delivery_date=None, is_hazardous=None, is_high_value=None):
    start_time = time.time()

    logging.info(f"Search initiated with filters - Trailer Type: {trailer_type}, Origin: {origin_city}, {origin_state}, Destination: {destination_city}, {destination_state}, Pickup Date: {pickup_date}, Delivery Date: {delivery_date}, Hazardous: {is_hazardous}, High Value: {is_high_value}")

    # Merge the two dataframes on LOAD_ID to allow filtering based on both data sources
    merged_data = pd.merge(load_posting, load_stop, on='LOAD_ID', suffixes=('_posting', '_stop'))

    # Filter by trailer type (cargo type)
    if trailer_type:
        merged_data = merged_data[merged_data['TRANSPORT_MODE'].str.contains(trailer_type, case=False)]
        logging.info(f"Filtered by trailer type '{trailer_type}', remaining records: {len(merged_data)}")

    # Filter by hazardous status
    if is_hazardous is not None:
        merged_data = merged_data[merged_data['IS_HAZARDOUS'] == is_hazardous]
        logging.info(f"Filtered by hazardous status '{is_hazardous}', remaining records: {len(merged_data)}")

    # Filter by high value
    if is_high_value is not None:
        merged_data = merged_data[merged_data['IS_HIGH_VALUE'] == is_high_value]
        logging.info(f"Filtered by high value status '{is_high_value}', remaining records: {len(merged_data)}")

    # Initialize origin and destination filtered data
    origin_filtered = merged_data
    destination_filtered = merged_data

    # Filter by origin city/state (pickup: STOP_TYPE == 'P')
    if origin_city:
        origin_filtered = origin_filtered[
            (origin_filtered['CITY'].str.contains(origin_city, case=False, na=False)) &
            (origin_filtered['STOP_SEQUENCE'] == 1) &
            (origin_filtered['STOP_TYPE'] == 'P')
        ]
        logging.info(f"Filtered by origin city '{origin_city}' for pickup, remaining records: {len(origin_filtered)}")
    if origin_state:
        origin_filtered = origin_filtered[
            (origin_filtered['STATE'].str.contains(origin_state, case=False, na=False)) &
            (origin_filtered['STOP_TYPE'] == 'P')
        ]
        logging.info(f"Filtered by origin state '{origin_state}' for pickup, remaining records: {len(origin_filtered)}")

    # Filter by destination city/state (drop-off: STOP_TYPE == 'D')
    if destination_city:
        destination_filtered = destination_filtered[
            (destination_filtered['CITY'].str.contains(destination_city, case=False, na=False)) &
            (destination_filtered['STOP_SEQUENCE'] == destination_filtered['STOP_SEQUENCE'].max()) &
            (destination_filtered['STOP_TYPE'] == 'D')
        ]
        logging.info(f"Filtered by destination city '{destination_city}' for drop-off, remaining records: {len(destination_filtered)}")
    if destination_state:
        destination_filtered = destination_filtered[
            (destination_filtered['STATE'].str.contains(destination_state, case=False, na=False)) &
            (destination_filtered['STOP_TYPE'] == 'D')
        ]
        logging.info(f"Filtered by destination state '{destination_state}' for drop-off, remaining records: {len(destination_filtered)}")

    # Combine the filtered origin and destination data
    filtered_data = pd.merge(origin_filtered, destination_filtered, on='LOAD_ID', suffixes=('_origin', '_destination'))

    # Apply pickup and delivery date filters
    if pickup_date and is_valid_date(pickup_date):
        filtered_data = filtered_data[filtered_data['APPOINTMENT_FROM_origin'].str.contains(pickup_date)]
        logging.info(f"Filtered by pickup date '{pickup_date}', remaining records: {len(filtered_data)}")
    if delivery_date and is_valid_date(delivery_date):
        filtered_data = filtered_data[filtered_data['APPOINTMENT_TO_destination'].str.contains(delivery_date)]
        logging.info(f"Filtered by delivery date '{delivery_date}', remaining records: {len(filtered_data)}")

    search_time = time.time() - start_time
    logging.info(f"Search completed in {search_time} seconds, final result count: {len(filtered_data)}")
    return filtered_data, search_time


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        trailer_type = request.form.get('trailer_type')
        origin_city = request.form.get('origin_city')
        origin_state = request.form.get('origin_state')
        destination_city = request.form.get('destination_city')
        destination_state = request.form.get('destination_state')
        pickup_date = request.form.get('pickup_date')
        delivery_date = request.form.get('delivery_date')
        is_hazardous = request.form.get('is_hazardous') == 'on'
        is_high_value = request.form.get('is_high_value') == 'on'

        # Perform the enhanced search
        results, search_time = enhanced_search(trailer_type, origin_city, origin_state, destination_city, destination_state, pickup_date, delivery_date, is_hazardous, is_high_value)

        # Debug: Print the number of results
        logging.info(f"Number of results found: {len(results)}")

        # If no results, show a "No results found" message
        if results.empty:
            results_html = "<p>No results found.</p>"
        else:
            # Display all results
            results_html = results.to_html(index=False)

        # Render the template with the search results and search time
        return render_template('index.html', results=results_html, search_time=search_time)

    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
