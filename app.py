import base64
from io import BytesIO
from flask import Flask, request, render_template, flash, redirect, url_for
from pcmiller import mapGenerator  # Ensure pcmiller.py is correctly placed
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pickle
import os
import sys
from dotenv import load_dotenv  # Import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Securely obtain the secret key from an environment variable
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    print("Error: The SECRET_KEY environment variable is not set.")
    print("Please set it to a secure random value and restart the application.")
    sys.exit(1)
app.secret_key = secret_key

# Load CSV data with correct delimiter
delimiter = ','  # Comma-separated
try:
    posting_data = pd.read_csv("./load_posting.csv", sep=delimiter)
    stop_data = pd.read_csv("./load_stop.csv", sep=delimiter)
    print(f"Loaded {len(posting_data)} records from load_posting.csv")
    print(f"Columns in load_posting.csv: {posting_data.columns.tolist()}")
    print(f"Loaded {len(stop_data)} records from load_stop.csv")
    print(f"Columns in load_stop.csv: {stop_data.columns.tolist()}")
except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit(1)
except pd.errors.ParserError as e:
    print(f"Error parsing CSV files: {e}")
    sys.exit(1)

# Load precomputed city coordinates
try:
    with open('city_coords.pkl', 'rb') as f:
        city_coords = pickle.load(f)
    print(f"Loaded {len(city_coords)} city coordinates from city_coords.pkl")
    # Print sample keys for verification
    print("Sample keys from city_coords.pkl:")
    for i, key in enumerate(list(city_coords.keys())[:10]):
        print(f"{i+1}: {key}")
except FileNotFoundError:
    print("Error: 'city_coords.pkl' not found. Please run 'precompute_coords.py' first.")
    sys.exit(1)
except Exception as e:
    print(f"Error loading 'city_coords.pkl': {e}")
    sys.exit(1)

# Initialize geolocator
geolocator = Nominatim(user_agent="freight_load_search_app")
coordinate_cache = {}  # Cache for origin/destination coordinates

def get_coordinates(city, state):
    """
    Retrieve coordinates for the given city and state.
    """
    city_state = f"{city}, {state}"
    if city_state in coordinate_cache:
        return coordinate_cache[city_state]
    else:
        # Check if city_state exists in precomputed city_coords
        formatted_city_state = f"{city.title()}, {state.upper()}"
        if formatted_city_state in city_coords:
            coordinate_cache[city_state] = city_coords[formatted_city_state]
            return city_coords[formatted_city_state]
        else:
            # Perform real-time geocoding as a fallback
            location = geolocator.geocode(city_state)
            if location:
                coords = (location.latitude, location.longitude)
                coordinate_cache[city_state] = coords
                # Optionally, update city_coords.pkl with new entry
                city_coords[formatted_city_state] = coords
                print(f"Coordinates for {formatted_city_state}: {coords}")
                return coords
            else:
                print(f"Could not find coordinates for {formatted_city_state}")
                coordinate_cache[city_state] = None
                return None

def testing(type_truck, radius, weight, posting_data, stop_data, origin_city, origin_state, dest_city, dest_state):
    """
    Filter and return load postings based on search criteria.
    """
    print("\n--- Starting Search ---")
    print(f"Type of Truck: {type_truck}")
    print(f"Radius: {radius} miles")
    print(f"Weight: {weight}")
    print(f"Origin: {origin_city}, {origin_state}")
    print(f"Destination: {dest_city}, {dest_state}")

    # Convert radius and weight
    try:
        radius = float(radius)
    except ValueError:
        print(f"Invalid radius value: {radius}. Using default radius of 25 miles.")
        radius = 25.0

    try:
        weight = float(weight) if weight else None
    except ValueError:
        print(f"Invalid weight value: {weight}. Ignoring weight filter.")
        weight = None

    # Filter by transport mode (case-insensitive)
    filtered_posting = posting_data[posting_data['TRANSPORT_MODE'].str.lower() == type_truck.lower()]
    print(f"After filtering by transport mode '{type_truck}': {len(filtered_posting)} records")

    # Filter by weight
    if weight:
        filtered_posting = filtered_posting[filtered_posting['TOTAL_WEIGHT'] <= weight]
        print(f"After filtering by weight <= {weight}: {len(filtered_posting)} records")

    # Merge data on LOAD_ID
    merged_data = pd.merge(filtered_posting, stop_data, on='LOAD_ID')
    print(f"After merging with stop data: {len(merged_data)} records")

    # Get origin coordinates
    origin_coords = get_coordinates(origin_city, origin_state)
    if not origin_coords:
        print("Could not find coordinates for the origin city/state")
        return []

    # Identify pickup and dropoff stops
    pickups = merged_data[merged_data['STOP_TYPE'].str.upper() == 'P']
    dropoffs = merged_data[merged_data['STOP_TYPE'].str.upper() == 'D']

    # Assume the first pickup and the last dropoff per LOAD_ID
    pickups = pickups.sort_values(['LOAD_ID', 'STOP_SEQUENCE']).drop_duplicates('LOAD_ID', keep='first')
    dropoffs = dropoffs.sort_values(['LOAD_ID', 'STOP_SEQUENCE']).drop_duplicates('LOAD_ID', keep='last')

    print(f"Number of pickups: {len(pickups)}, Number of dropoffs: {len(dropoffs)}")

    # Merge pickups and dropoffs with posting_data
    postings_with_stops = pd.merge(
        filtered_posting,
        pickups[['LOAD_ID', 'CITY', 'STATE']],
        on='LOAD_ID',
        how='left',
        suffixes=('', '_pickup')
    )
    postings_with_stops = pd.merge(
        postings_with_stops,
        dropoffs[['LOAD_ID', 'CITY', 'STATE']],
        on='LOAD_ID',
        how='left',
        suffixes=('', '_dropoff')
    )

    # Rename columns for clarity
    postings_with_stops.rename(columns={
        'CITY': 'Pickup_City',
        'STATE': 'Pickup_State',
        'CITY_dropoff': 'Destination_City',
        'STATE_dropoff': 'Destination_State'
    }, inplace=True)

    # Add CITY_STATE column for pickup
    postings_with_stops['CITY_STATE'] = postings_with_stops['Pickup_City'].str.title().str.strip() + ', ' + postings_with_stops['Pickup_State'].str.upper().str.strip()

    # Map pickup coordinates from precomputed city_coords
    postings_with_stops['pickup_coords'] = postings_with_stops['CITY_STATE'].map(city_coords)
    
    # Debugging: Check how many mappings are successful
    print(f"Number of successful pickup_coords mappings: {postings_with_stops['pickup_coords'].notna().sum()}")

    # Drop records without pickup coordinates
    postings_with_stops = postings_with_stops.dropna(subset=['pickup_coords'])
    print(f"After mapping pickup coordinates: {len(postings_with_stops)} records")

    # Debugging: Print unmatched CITY_STATE values
    unmatched = postings_with_stops[postings_with_stops['pickup_coords'].isna()]
    if not unmatched.empty:
        print("Unmatched CITY_STATE values:")
        print(unmatched['CITY_STATE'].unique())
    else:
        print("All CITY_STATE values were successfully mapped.")

    # Calculate distances from origin to pickup locations
    postings_with_stops['distance'] = postings_with_stops['pickup_coords'].apply(lambda x: geodesic(origin_coords, x).miles)

    # Filter by radius
    postings_with_stops = postings_with_stops[postings_with_stops['distance'] <= radius]
    print(f"After filtering by radius <= {radius} miles: {len(postings_with_stops)} records")

    # Debugging: Print destination cities and states after radius filtering
    if not postings_with_stops.empty:
        print("Destination Cities and States after radius filtering:")
        print(postings_with_stops[['Destination_City', 'Destination_State']].drop_duplicates().head())
    else:
        print("No records found after radius filtering.")

    # Filter by destination city and state (case-insensitive)
    filtered_data = postings_with_stops[
        (postings_with_stops['Destination_City'].str.lower().str.strip() == dest_city.lower().strip()) &
        (postings_with_stops['Destination_State'].str.lower().str.strip() == dest_state.lower().strip())
    ]
    print(f"After filtering by destination: {len(filtered_data)} records")

    results = filtered_data.to_dict('records')
    print(f"Total results found: {len(results)}")
    print("--- Search Completed ---\n")
    return results

@app.route('/', methods=['GET', 'POST'])
def index():
    map_image = None
    results = []
    type_truck = 'Dry Van'
    radius = 25
    origin_city = ''
    origin_state = ''
    dest_city = ''
    dest_state = ''
    weight = 0

    if request.method == 'POST':
        # Get form data and strip leading/trailing whitespaces
        origin_city = request.form.get('origin_city', '').strip()
        origin_state = request.form.get('origin_state', '').strip()
        dest_city = request.form.get('dest_city', '').strip()
        dest_state = request.form.get('dest_state', '').strip()
        type_truck = request.form.get('type_truck', 'Dry Van').strip()
        radius = request.form.get('radius', 25)
        weight = request.form.get('weight', 0)

        # Validate required fields
        if not (origin_city and origin_state and dest_city and dest_state):
            print("Missing required search parameters.")
            flash("Please fill in all required search parameters.", "warning")
            return redirect(url_for('index'))
        else:
            # Prepare stops for map generation
            stops = [
                {"City": origin_city, "State": origin_state},
                {"City": dest_city, "State": dest_state}
            ]

            # Generate the map image
            img = mapGenerator(stops)
            if img:
                # Convert PIL Image to base64 string
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()
                map_image = base64.b64encode(img_bytes).decode('utf-8')
            else:
                map_image = None

            # Call the testing function to get search results
            results = testing(
                type_truck,
                radius,
                weight,
                posting_data,
                stop_data,
                origin_city,
                origin_state,
                dest_city,
                dest_state
            )

            if not results:
                flash("No loads available for the selected criteria. Please refine your search.", "info")

    # Extract unique cities and states for dynamic dropdowns from stop_data
    unique_origin_cities = sorted(stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']['CITY'].dropna().unique().tolist())
    unique_origin_states = sorted(stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']['STATE'].dropna().unique().tolist())
    unique_dest_cities = sorted(stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']['CITY'].dropna().unique().tolist())
    unique_dest_states = sorted(stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']['STATE'].dropna().unique().tolist())

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
        unique_origin_states=unique_origin_states,
        unique_dest_cities=unique_dest_cities,
        unique_dest_states=unique_dest_states
    )

if __name__ == '__main__':
    app.run(debug=True)

