import base64
from io import BytesIO
from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
from pcmiller import mapGenerator
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pickle
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Securely obtain the secret key from an environment variable
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    print("Error: The SECRET_KEY environment variable is not set.")
    sys.exit(1)
app.secret_key = secret_key

# Load CSV data with debugging
try:
    posting_data = pd.read_csv("load_posting.csv")
    stop_data = pd.read_csv("load_stop.csv")
    print(f"Loaded {len(posting_data)} records from load_posting.csv")
    print(f"Loaded {len(stop_data)} records from load_stop.csv")
except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit(1)

# Ensure LOAD_ID columns are strings
posting_data['LOAD_ID'] = posting_data['LOAD_ID'].astype(str)
stop_data['LOAD_ID'] = stop_data['LOAD_ID'].astype(str)


# Load precomputed city coordinates
try:
    with open('city_coords.pkl', 'rb') as f:
        city_coords = pickle.load(f)
    print(f"Loaded {len(city_coords)} city coordinates from city_coords.pkl")
except FileNotFoundError:
    print("Error: 'city_coords.pkl' not found. Please run 'precompute_coords.py' first.")
    sys.exit(1)

# Create a DataFrame containing only the routes that exist between pickup and drop-off locations
routes = pd.merge(
    stop_data[stop_data['STOP_TYPE'].str.upper() == 'P'][['LOAD_ID', 'CITY', 'STATE']],
    stop_data[stop_data['STOP_TYPE'].str.upper() == 'D'][['LOAD_ID', 'CITY', 'STATE']],
    on='LOAD_ID',
    suffixes=('_origin', '_dest')
)

# Initialize geolocator
geolocator = Nominatim(user_agent="freight_load_search_app")
coordinate_cache = {}

def get_postings_with_stops(filtered_posting, stop_data):
    # Filter pickups and dropoffs
    pickups = stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']
    dropoffs = stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']

    # Keep only the first pickup and last dropoff for each LOAD_ID
    pickups = pickups.sort_values(['LOAD_ID', 'STOP_SEQUENCE']).drop_duplicates('LOAD_ID', keep='first').reset_index(drop=True)
    dropoffs = dropoffs.sort_values(['LOAD_ID', 'STOP_SEQUENCE']).drop_duplicates('LOAD_ID', keep='last').reset_index(drop=True)

    # Rename columns in pickups and dropoffs
    pickups = pickups.rename(columns={'CITY': 'Pickup_City', 'STATE': 'Pickup_State'})
    dropoffs = dropoffs.rename(columns={'CITY': 'Destination_City', 'STATE': 'Destination_State'})

    # Merge pickups and dropoffs back with filtered_posting
    postings_with_stops = pd.merge(
        filtered_posting,
        pickups[['LOAD_ID', 'Pickup_City', 'Pickup_State']],
        on='LOAD_ID',
        how='left'
    )
    postings_with_stops = pd.merge(
        postings_with_stops,
        dropoffs[['LOAD_ID', 'Destination_City', 'Destination_State']],
        on='LOAD_ID',
        how='left'
    )

    return postings_with_stops


def get_coordinates(city, state):
    """Retrieve coordinates for the given city and state."""
    city_state = f"{city}, {state}"
    if city_state in coordinate_cache:
        return coordinate_cache[city_state]
    elif city_state in city_coords:
        coordinate_cache[city_state] = city_coords[city_state]
        return city_coords[city_state]
    else:
        location = geolocator.geocode(city_state)
        if location:
            coords = (location.latitude, location.longitude)
            coordinate_cache[city_state] = coords
            return coords
        else:
            print(f"Could not find coordinates for {city_state}")
            return None

def search_loads(type_truck, radius, weight, posting_data, stop_data, origin_city='', origin_state='', dest_city='', dest_state=''):
    """Filter and return load postings based on search criteria."""
    print("\n--- Starting Search ---")
    print(f"Type of Truck: {type_truck}")
    print(f"Radius: {radius} miles")
    print(f"Weight: {weight}")
    print(f"Origin: {origin_city}, {origin_state}")
    print(f"Destination: {dest_city}, {dest_state}")

    # Filter by transport mode
    filtered_posting = posting_data[posting_data['TRANSPORT_MODE'].str.lower() == type_truck.lower()]
    print(f"After filtering by transport mode '{type_truck}': {len(filtered_posting)} records")

    # Filter by weight
    if weight > 0:
        filtered_posting = filtered_posting[filtered_posting['TOTAL_WEIGHT'] <= weight]
        print(f"After filtering by weight <= {weight}: {len(filtered_posting)} records")

    if filtered_posting.empty:
        print("No postings after filtering by transport mode and weight.")
        return []

    # Get postings with stops
    postings_with_stops = get_postings_with_stops(filtered_posting, stop_data)

    # Check if postings_with_stops is empty
    if postings_with_stops.empty:
        print("No postings after merging pickups and dropoffs.")
        return []

    # Calculate distances from origin to pickup location
    if origin_city and origin_state:
        origin_coords = get_coordinates(origin_city, origin_state)
        if not origin_coords:
            print("Could not find coordinates for the origin city/state")
            return []
        postings_with_stops['distance'] = postings_with_stops.apply(
            lambda row: geodesic(origin_coords, get_coordinates(row['Pickup_City'], row['Pickup_State'])).miles
            if pd.notna(row['Pickup_City']) and pd.notna(row['Pickup_State']) else None, axis=1
        )

        # Filter by radius
        postings_with_stops = postings_with_stops[postings_with_stops['distance'] <= radius]
        print(f"After filtering by radius <= {radius} miles: {len(postings_with_stops)} records")

    else:
        print("Origin city and state not provided; skipping distance calculation.")

    # Initialize filtered_data
    filtered_data = postings_with_stops.copy()

    # Debug: Print available cities and states
    print("Available Pickup Cities after radius filtering:", filtered_data['Pickup_City'].unique())
    print("Available Pickup States after radius filtering:", filtered_data['Pickup_State'].unique())
    print("Available Destination Cities after radius filtering:", filtered_data['Destination_City'].unique())
    print("Available Destination States after radius filtering:", filtered_data['Destination_State'].unique())

    # Prepare input parameters
    origin_city_clean = origin_city.strip().lower()
    origin_state_clean = origin_state.strip().lower()
    dest_city_clean = dest_city.strip().lower()
    dest_state_clean = dest_state.strip().lower()

    # Adjust filtering logic as previously discussed
    if not (origin_city and origin_state and radius > 0):
        # Filter by origin city and state if provided
        if origin_city:
            filtered_data = filtered_data[filtered_data['Pickup_City'].str.strip().str.lower() == origin_city_clean]
        if origin_state:
            filtered_data = filtered_data[filtered_data['Pickup_State'].str.strip().str.lower() == origin_state_clean]

    # Filter by destination city and state if provided
    if dest_city:
        filtered_data = filtered_data[filtered_data['Destination_City'].str.strip().str.lower() == dest_city_clean]
    if dest_state:
        filtered_data = filtered_data[filtered_data['Destination_State'].str.strip().str.lower() == dest_state_clean]

    print(f"After filtering by origin and destination: {len(filtered_data)} records")

    if filtered_data.empty:
        print("No postings after all filtering.")
        return []

    return filtered_data.to_dict('records')


def get_suggestions(origin_city, origin_state, transport_mode):
    """Provide alternate suggestions based on the current data."""
    # Since we have the routes DataFrame, use it to find top routes
    top_routes = (
        routes
        .groupby(['CITY_origin', 'STATE_origin', 'CITY_dest', 'STATE_dest'])
        .size()
        .reset_index(name='count')
        .sort_values(by='count', ascending=False)
    )
    return top_routes.head(5).to_dict(orient='records')

@app.route('/', methods=['GET', 'POST'])
def index():
    # Initialize variables
    map_image = None
    results = []
    type_truck = 'Dry Van'
    radius = 200
    origin_city = ''
    origin_state = ''
    dest_city = ''
    dest_state = ''
    weight = 0

    if request.method == 'POST':
        # Fetch form data and sanitize inputs
        origin_city = request.form.get('origin_city', '').strip()
        origin_state = request.form.get('origin_state', '').strip()
        dest_city = request.form.get('dest_city', '').strip()
        dest_state = request.form.get('dest_state', '').strip()
        type_truck = request.form.get('type_truck', 'Dry Van').strip()
        radius = float(request.form.get('radius', 200))
        weight = float(request.form.get('weight', 0))

        # Validate required inputs
        if not (origin_city or dest_city):
            flash("Please provide at least an origin or destination city.", "warning")
            return redirect(url_for('index'))
        if radius > 0:
            origin_city=''
            origin_state=''

        # Perform the search
        results = search_loads(
            type_truck, radius, weight,
            posting_data, stop_data,
            origin_city, origin_state, dest_city, dest_state
        )

        if not results:
            flash("No loads available for the selected criteria. Please refine your search.", "info")
        else:
            flash(f"Found {len(results)} loads matching your criteria.", "info")

    # Extract unique cities and states for dropdowns
    unique_origin_cities = routes['CITY_origin'].dropna().unique().tolist()
    unique_dest_cities = routes['CITY_dest'].dropna().unique().tolist()

    # Sort the city lists for better user experience
    unique_origin_cities.sort()
    unique_dest_cities.sort()

    # Render the template
    return render_template(
        'index.html',
        map_image=map_image,
        results=results,
        type_truck=type_truck,
        radius=radius,
        origin_city=origin_city,
        origin_state=origin_state,
        dest_city=dest_city,
        dest_state=dest_state,
        unique_origin_cities=unique_origin_cities,
        unique_dest_cities=unique_dest_cities
    )

@app.route('/dashboard')
def dashboard():
    # Transport mode distribution - Using posting_data
    transport_mode_counts = {}
    if 'TRANSPORT_MODE' in posting_data.columns:
        transport_mode_counts = posting_data['TRANSPORT_MODE'].value_counts().to_dict()
        print("Transport Mode Counts:", transport_mode_counts)  # Debugging

    # Top pickup cities (using stop_data)
    pickup_stats = {}
    if 'STOP_TYPE' in stop_data.columns and 'CITY' in stop_data.columns:
        pickup_stats = stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']['CITY'].value_counts().head(10).to_dict()
        print("Top Pickup Cities:", pickup_stats)  # Debugging

    # Top drop-off cities (using stop_data)
    dropoff_stats = {}
    if 'STOP_TYPE' in stop_data.columns and 'CITY' in stop_data.columns:
        dropoff_stats = stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']['CITY'].value_counts().head(10).to_dict()
        print("Top Drop-off Cities:", dropoff_stats)  # Debugging

    # Merge postings with pickups and dropoffs to get Origin and Destination cities
    pickups = stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']
    dropoffs = stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']

    pickups = pickups.sort_values(['LOAD_ID', 'STOP_SEQUENCE']).drop_duplicates('LOAD_ID', keep='first')
    dropoffs = dropoffs.sort_values(['LOAD_ID', 'STOP_SEQUENCE']).drop_duplicates('LOAD_ID', keep='last')

    postings_with_stops = pd.merge(
        posting_data,
        pickups[['LOAD_ID', 'CITY', 'STATE']],
        on='LOAD_ID',
        how='left'
    )
    postings_with_stops = pd.merge(
        postings_with_stops,
        dropoffs[['LOAD_ID', 'CITY', 'STATE']],
        on='LOAD_ID',
        how='left',
        suffixes=('_origin', '_dest')
    )

    # Rename columns for clarity
    postings_with_stops.rename(columns={
        'CITY_origin': 'Origin_City',
        'STATE_origin': 'Origin_State',
        'CITY_dest': 'Dest_City',
        'STATE_dest': 'Dest_State'
    }, inplace=True)

    # Now we can compute active routes using postings_with_stops
    active_routes = []
    if {'Origin_City', 'Origin_State', 'Dest_City', 'Dest_State'}.issubset(postings_with_stops.columns):
        active_routes = (
            postings_with_stops.groupby(['Origin_City', 'Origin_State', 'Dest_City', 'Dest_State'])
            .size()
            .reset_index(name='count')
            .sort_values(by='count', ascending=False)
            .head(10)
            .to_dict(orient='records')
        )
        print("Top City Pairs with Active Routes:", active_routes)  # Debugging

    # Average weight by transport mode
    avg_weight_by_mode = []
    if 'TRANSPORT_MODE' in postings_with_stops.columns and 'TOTAL_WEIGHT' in postings_with_stops.columns:
        avg_weight_by_mode = (
            postings_with_stops.groupby('TRANSPORT_MODE')['TOTAL_WEIGHT']
            .mean()
            .reset_index()
            .rename(columns={'TOTAL_WEIGHT': 'average_weight'})
            .to_dict(orient='records')
        )
        print("Average Weight by Transport Mode:", avg_weight_by_mode)  # Debugging

    # Pass all variables to the dashboard template
    return render_template(
        'dashboard.html',
        transport_mode_counts=transport_mode_counts,
        pickup_stats=pickup_stats,
        dropoff_stats=dropoff_stats,
        avg_weight_by_mode=avg_weight_by_mode,
        active_routes=active_routes
    )

@app.route('/get_states_for_city', methods=['GET'])
def get_states_for_city():
    city = request.args.get('city')
    location_type = request.args.get('type')  # 'origin' or 'dest'
    if location_type == 'origin':
        states = routes[routes['CITY_origin'] == city]['STATE_origin'].dropna().unique().tolist()
    else:
        states = routes[routes['CITY_dest'] == city]['STATE_dest'].dropna().unique().tolist()
    return jsonify({'states': states})

@app.route('/get_map', methods=['GET'])
def get_map():
    load_id = request.args.get('load_id')
    if not load_id:
        return "Invalid Load ID", 400

    # Ensure load_id is a string
    load_id = str(load_id)

    # Get postings with stops
    postings_with_stops = get_postings_with_stops(posting_data, stop_data)

    print(f"Available LOAD_IDs in postings_with_stops: {postings_with_stops['LOAD_ID'].unique()}")

    # Filter for the specific load_id
    load = postings_with_stops[postings_with_stops['LOAD_ID'] == load_id]
    if load.empty:
        print(f"Load ID {load_id} not found in postings_with_stops")
        return "No route found for the given Load ID", 404

    # Use the correct column names
    stops = [
        {"City": load.iloc[0]['Pickup_City'], "State": load.iloc[0]['Pickup_State']},
        {"City": load.iloc[0]['Destination_City'], "State": load.iloc[0]['Destination_State']}
    ]
    img = mapGenerator(stops)
    if img:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return buffered.getvalue(), 200, {'Content-Type': 'image/png'}
    return "Failed to generate map", 500


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)
