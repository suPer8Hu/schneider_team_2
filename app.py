import base64
from io import BytesIO
import logging
from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pickle
import os
import sys
from dotenv import load_dotenv
from cachetools import cached, LRUCache
from multiprocessing import Pool
from flask import request, redirect, url_for
from pcmiller import calculate_mileage, get_directions, mapGenerator
from utils import get_coordinates

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Securely obtain the secret key from an environment variable
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    logger.error("Error: The SECRET_KEY environment variable is not set.")
    sys.exit(1)
app.secret_key = secret_key

# Access the Google Maps API key
google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
if not google_maps_api_key:
    logger.error("Error: The GOOGLE_MAPS_API_KEY environment variable is not set.")
    sys.exit(1)
############################################################################
############################################################################
############################################################################
############################################################################
############################################################################
############################################################################

# Load CSV data with debugging
import boto3
import pandas as pd

# Initialize DynamoDB resource
dynamodb = boto3.resource(
    'dynamodb',
    region_name='us-east-2',

)

def load_data_from_table(table_name):
    """
    Load data from a DynamoDB table using scan.
    
    Parameters:
        table_name (str): Name of the DynamoDB table.
    
    Returns:
        list: List of items from the table.
    """
    table = dynamodb.Table(table_name)
    data = []
    response = table.scan()

    # Append data from the initial scan
    data.extend(response.get('Items', []))

    # Continue scanning if more data is available
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        data.extend(response.get('Items', []))
    
    return data

# Load data from DynamoDB tables
posting_data = load_data_from_table('load_postings')
stop_data = load_data_from_table('load_stops')

# Convert data to pandas DataFrames
posting_data = pd.DataFrame(posting_data)
stop_data = pd.DataFrame(stop_data)

# Display information about the loaded data
print(f"Loaded {len(posting_data)} records from 'load_posting'")
print(f"Loaded {len(stop_data)} records from 'load_stop'")
print(posting_data.head())
print(stop_data.head())




############################################################################
############################################################################
############################################################################
############################################################################
############################################################################
############################################################################







# Ensure LOAD_ID columns are strings
posting_data['LOAD_ID'] = posting_data['LOAD_ID'].astype(str)
stop_data['LOAD_ID'] = stop_data['LOAD_ID'].astype(str)

# # Load precomputed city coordinates
# try:
#     with open('city_coords.pkl', 'rb') as f:
#         city_coords = pickle.load(f)
#     logger.info(f"Loaded {len(city_coords)} city coordinates from city_coords.pkl")
# except FileNotFoundError:
#     logger.error("Error: 'city_coords.pkl' not found. Please run 'precompute_coords.py' first.")
#     sys.exit(1)

# Create a DataFrame containing only the routes that exist between pickup and drop-off locations
routes = pd.merge(
    stop_data[stop_data['STOP_TYPE'].str.upper() == 'P'][['LOAD_ID', 'CITY', 'STATE']],
    stop_data[stop_data['STOP_TYPE'].str.upper() == 'D'][['LOAD_ID', 'CITY', 'STATE']],
    on='LOAD_ID',
    suffixes=('_origin', '_dest')
)

# # Initialize geolocator
# geolocator = Nominatim(user_agent="freight_load_search_app")

# # Initialize an LRU cache for coordinates
# coordinate_cache = LRUCache(maxsize=10000)

# @cached(coordinate_cache)
# def get_coordinates(city, state):
#     """Retrieve coordinates for the given city and state."""
#     city_state = f"{city}, {state}"
#     if city_state in city_coords:
#         return city_coords[city_state]
#     else:
#         try:
#             location = geolocator.geocode(city_state, timeout=10)
#             if location:
#                 coords = (location.latitude, location.longitude)
#                 city_coords[city_state] = coords
#                 # Optionally, save updated coordinates to 'city_coords.pkl'
#                 with open('city_coords.pkl', 'wb') as f:
#                     pickle.dump(city_coords, f)
#                 return coords
#             else:
#                 logger.warning(f"Could not find coordinates for {city_state}")
#                 return None
#         except Exception as e:
#             logger.error(f"Geocoding error for {city_state}: {e}")
#             return None








def get_postings_with_stops(posting_data, stop_data):
    """
    Merge posting_data with stop_data to include pickup and destination details.
    """
    # Filter pickups and dropoffs
    pickups = stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']
    dropoffs = stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']

    # Keep only the first pickup and last dropoff for each LOAD_ID
    pickups = pickups.sort_values(['LOAD_ID', 'STOP_SEQUENCE'])
    pickups = pickups.drop_duplicates('LOAD_ID', keep='first')
    pickups.reset_index(drop=True, inplace=True)

    dropoffs = dropoffs.sort_values(['LOAD_ID', 'STOP_SEQUENCE'])
    dropoffs = dropoffs.drop_duplicates('LOAD_ID', keep='last')
    dropoffs.reset_index(drop=True, inplace=True)

    # Rename columns in pickups and dropoffs
    pickups = pickups.rename(columns={
        'CITY': 'Pickup_City',
        'STATE': 'Pickup_State'
    })
    dropoffs = dropoffs.rename(columns={
        'CITY': 'Destination_City',
        'STATE': 'Destination_State'
    })

    # Merge pickups and dropoffs back with posting_data
    postings_with_stops = pd.merge(
        posting_data,
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

    # Fill NaN values with empty strings to prevent template errors
    postings_with_stops.fillna({
        'Pickup_City': '',
        'Pickup_State': '',
        'Destination_City': '',
        'Destination_State': ''
    }, inplace=True)

    # Ensure all relevant fields are strings
    string_fields = [
        'Pickup_City', 'Pickup_State',
        'Destination_City', 'Destination_State'
    ]
    for field in string_fields:
        postings_with_stops[field] = postings_with_stops[field].astype(str)

    return postings_with_stops



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


def search_loads(
    type_truck, radius, weight, posting_data, stop_data,
    origin_city='', origin_state='', dest_city='', dest_state='',
    page=1, per_page=20
):
    """
    Filter and return load postings based on search criteria with pagination.

    Parameters:
        type_truck (str): Type of truck (e.g., 'Dry Van').
        radius (float): Search radius in miles.
        weight (float): Maximum load weight in lbs.
        posting_data (DataFrame): DataFrame containing load postings.
        stop_data (DataFrame): DataFrame containing stop information.
        origin_city (str): Origin city name.
        origin_state (str): Origin state abbreviation.
        dest_city (str): Destination city name.
        dest_state (str): Destination state abbreviation.
        page (int): Current page number.
        per_page (int): Number of items per page.

    Returns:
        tuple: (List of matching load records for the current page, total number of records, 
                loads_available_in_origin_state, loads_available_in_dest_state)
    """
    logger.info("\n--- Starting Search ---")
    logger.info(f"Type of Truck: {type_truck}")
    logger.info(f"Radius: {radius} miles")
    logger.info(f"Weight: {weight}")
    logger.info(f"Origin: {origin_city}, {origin_state}")
    logger.info(f"Destination: {dest_city}, {dest_state}")
    logger.info(f"Page: {page}, Per Page: {per_page}")

    # Base case: No filters applied, return all available routes
    if not origin_city and not origin_state and not dest_city and not dest_state:
        logger.info("Base case: No filters applied, returning all available routes.")
        all_routes = posting_data.copy()
        postings_with_stops = get_postings_with_stops(all_routes, stop_data)
        total = len(postings_with_stops)
        # Apply pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated_results = postings_with_stops.iloc[start:end].to_dict('records')
        logger.info(f"Total records: {total}, Paginated records: {len(paginated_results)}")
        return paginated_results, total, False, False  # No state-specific loads

    # Filter by transport mode
    filtered_posting = posting_data[
        posting_data['TRANSPORT_MODE'].str.lower() == type_truck.lower()
    ]
    logger.info(f"After filtering by transport mode '{type_truck}': {len(filtered_posting)} records")

    # Filter by weight
    if weight and weight > 0:
        filtered_posting = filtered_posting[filtered_posting['TOTAL_WEIGHT'] <= weight]
        logger.info(f"After filtering by weight <= {weight}: {len(filtered_posting)} records")
    else:
        logger.info("No weight filtering applied.")

    if filtered_posting.empty:
        logger.info("No postings after filtering by transport mode and weight.")
        return [], 0, False, False  # Return empty list and False flags

    # Get postings with stops
    postings_with_stops = get_postings_with_stops(filtered_posting, stop_data)
    logger.info(f"Postings with stops: {len(postings_with_stops)} records")

    if postings_with_stops.empty:
        logger.info("No postings after merging pickups and dropoffs.")
        return [], 0, False, False  # Return empty list and False flags

    # Initialize filtered_data
    filtered_data = postings_with_stops.copy()

    # Prepare input parameters
    origin_city_clean = origin_city.strip().lower()
    origin_state_clean = origin_state.strip().lower()
    dest_city_clean = dest_city.strip().lower()
    dest_state_clean = dest_state.strip().lower()

    # Ensure city and state names are consistent
    filtered_data['Pickup_City'] = filtered_data['Pickup_City'].str.strip().str.lower()
    filtered_data['Pickup_State'] = filtered_data['Pickup_State'].str.strip().str.lower()
    filtered_data['Destination_City'] = filtered_data['Destination_City'].str.strip().str.lower()
    filtered_data['Destination_State'] = filtered_data['Destination_State'].str.strip().str.lower()

    logger.info(f"Unique Pickup Cities: {filtered_data['Pickup_City'].unique()}")
    logger.info(f"Unique Pickup States: {filtered_data['Pickup_State'].unique()}")

    # Initialize flags
    loads_available_in_origin_state = False
    loads_available_in_dest_state = False

    # Initial filtering by origin
    if origin_city:
        # Attempt to filter by exact city and state
        if origin_state:
            city_state_filter = (
                (filtered_data['Pickup_City'] == origin_city_clean) &
                (filtered_data['Pickup_State'] == origin_state_clean)
            )
            filtered_data_city = filtered_data[city_state_filter]
            logger.info(f"After filtering by origin city and state: {len(filtered_data_city)} records")
        else:
            # If only city is provided
            filtered_data_city = filtered_data[
                filtered_data['Pickup_City'] == origin_city_clean
            ]
            logger.info(f"After filtering by origin city: {len(filtered_data_city)} records")

        if not filtered_data_city.empty:
            filtered_data = filtered_data_city
        elif radius > 0:
            # Apply radius filtering
            origin_coords = get_coordinates(origin_city, origin_state)
            if not origin_coords:
                logger.info("Could not find coordinates for the origin city/state")
                return [], 0, False, False

            # Get coordinates for all pickup locations
            filtered_data['Pickup_Coords'] = filtered_data.apply(
                lambda row: get_coordinates(row['Pickup_City'], row['Pickup_State']),
                axis=1
            )

            # Remove records with missing coordinates
            filtered_data = filtered_data[filtered_data['Pickup_Coords'].notnull()]

            # Calculate distances
            filtered_data['distance'] = filtered_data['Pickup_Coords'].apply(
                lambda coords: geodesic(origin_coords, coords).miles
            )
            
            # Filter by radius
            filtered_data = filtered_data[filtered_data['distance'] <= radius]
            print(filtered_data)
            logger.info(f"After applying radius <= {radius} miles: {len(filtered_data)} records")
        else:
            # No loads in city and no radius specified
            logger.info("No loads found in the specified origin city/state, and no radius specified.")
            filtered_data = pd.DataFrame()

    elif origin_state:
        # Filter by origin state
        filtered_data = filtered_data[
            filtered_data['Pickup_State'] == origin_state_clean
        ]
        logger.info(f"After filtering by origin state: {len(filtered_data)} records")

    else:
        logger.info("No origin city or state provided. Considering all origins.")

    # Check if there are loads in the origin state (regardless of city)
    if origin_state and not loads_available_in_origin_state:
        origin_state_loads = posting_data[
            posting_data['LOAD_ID'].isin(stop_data[
                (stop_data['STOP_TYPE'].str.upper() == 'P') &
                (stop_data['STATE'].str.strip().str.lower() == origin_state_clean)
            ]['LOAD_ID'])
        ]
        if not origin_state_loads.empty:
            loads_available_in_origin_state = True

    # Filter by destination
    if dest_state:
        filtered_data = filtered_data[
            filtered_data['Destination_State'] == dest_state_clean
        ]
        logger.info(f"After filtering by destination state '{dest_state}': {len(filtered_data)} records")
    if dest_city:
        filtered_data = filtered_data[
            filtered_data['Destination_City'] == dest_city_clean
        ]
        logger.info(f"After filtering by destination city '{dest_city}': {len(filtered_data)} records")
    else:
        logger.info("No destination city provided or filtering applied.")

    # Check if there are loads destined for the destination state
    if not filtered_data.empty:
        # Loads are available after destination filtering
        pass
    elif dest_state:
        dest_state_loads = posting_data[
            posting_data['LOAD_ID'].isin(stop_data[
                (stop_data['STOP_TYPE'].str.upper() == 'D') &
                (stop_data['STATE'].str.strip().str.lower() == dest_state_clean)
            ]['LOAD_ID'])
        ]
        if not dest_state_loads.empty:
            loads_available_in_dest_state = True

    # Debug: Print available cities and states after filtering
    logger.info("Available Pickup Cities after filtering: {}".format(filtered_data['Pickup_City'].unique()))
    logger.info("Available Pickup States after filtering: {}".format(filtered_data['Pickup_State'].unique()))
    logger.info("Available Destination Cities after filtering: {}".format(filtered_data['Destination_City'].unique()))
    logger.info("Available Destination States after filtering: {}".format(filtered_data['Destination_State'].unique()))

    if filtered_data.empty:
        logger.info("No postings after all filtering.")
        return [], 0, loads_available_in_origin_state, loads_available_in_dest_state

    # Drop the 'distance' and 'Pickup_Coords' columns if they exist before returning results
    columns_to_drop = ['distance', 'Pickup_Coords']
    for col in columns_to_drop:
        if col in filtered_data.columns:
            filtered_data = filtered_data.drop(columns=[col])

    # Calculate total results before pagination
    total = len(filtered_data)

    # Apply pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated_data = filtered_data.iloc[start:end].to_dict('records')

    logger.info(f"Returning {len(paginated_data)} records out of {total} total matching records.")
    return paginated_data, total, loads_available_in_origin_state, loads_available_in_dest_state

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
    weight = 25000  # Default weight

    type_truck = request.cookies.get('type_truck', 'Dry Van')
    radius = float(request.cookies.get('radius', 200))
    weight = float(request.cookies.get('weight', 25000))
    origin_city = request.cookies.get('origin_city', '')
    origin_state = request.cookies.get('origin_state', '')
    dest_city = request.cookies.get('dest_city', '')
    dest_state = request.cookies.get('dest_state', '')
    
    # Initialize flags
    loads_in_origin_state = False
    loads_in_dest_state = False

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20  # You can make this configurable

    # Flag to indicate if a search has been performed
    search_performed = False

    if request.method == 'POST':
        # Fetch form data and sanitize inputs
        origin_city = request.form.get('origin_city', '').strip()
        origin_state = request.form.get('origin_state', '').strip()
        dest_city = request.form.get('dest_city', '').strip()
        dest_state = request.form.get('dest_state', '').strip()
        type_truck = request.form.get('type_truck', '').strip() or 'Dry Van'
        radius = float(request.form.get('radius', 200))
        weight = float(request.form.get('weight', 25000))
        
        response = redirect(url_for('index', page=page))
        response.set_cookie('type_truck', type_truck, max_age=3600)  # Expires in 1 hour
        response.set_cookie('radius', str(radius), max_age=3600)
        response.set_cookie('weight', str(weight), max_age=3600)
        response.set_cookie('origin_city', origin_city, max_age=3600)
        response.set_cookie('origin_state', origin_state, max_age=3600)
        response.set_cookie('dest_city', dest_city, max_age=3600)
        response.set_cookie('dest_state', dest_state, max_age=3600)

        # Reset to first page upon new search
        page = 1

        # Check for the base case (all origin and destination)
        if not origin_city and not origin_state and not dest_city and not dest_state:
            flash("No filters applied. Showing all available routes.", "info")

        # Check if the user has selected to view state-level loads
        view_state_loads = request.form.get('view_state_loads', '')
        logger.info(f"View State Loads Button Value: {view_state_loads}")

        if view_state_loads == 'origin':
            # Modify the search to use the origin state only
            origin_city = ''
            dest_city = ''       # Reset destination city
            dest_state = ''      # Reset destination state
            radius = 0            # Ignore radius when searching by state
            flash(f"Showing loads from origin state: {origin_state}", "info")
        
        elif view_state_loads == 'destination':
            # Modify the search to use the destination state only
            dest_city = ''
            origin_city = ''     # Reset origin city
            origin_state = ''    # Reset origin state
            radius = 0            # Ignore radius when searching by state
            flash(f"Showing loads destined for destination state: {dest_state}", "info")

        # Perform the search
        results, total, loads_in_origin_state, loads_in_dest_state = search_loads(
            type_truck, radius, weight,
            posting_data, stop_data,
            origin_city, origin_state, dest_city, dest_state,
            page, per_page
        )

        # Indicate that a search has been performed
        search_performed = True

        if not results:
            messages = []
            if loads_in_origin_state and loads_in_dest_state:
                messages.append(
                    "No loads available between the specified origin and destination cities. "
                    "However, there are loads available in both the origin and destination states."
                )
            elif loads_in_origin_state and not loads_in_dest_state:
                messages.append(
                    "No loads available between the specified origin and destination cities. "
                    "However, there are loads available in the origin state. Please refine your origin criteria."
                )
            elif loads_in_dest_state and not loads_in_origin_state:
                messages.append(
                    "No loads available between the specified origin and destination cities. "
                    "However, there are loads available in the destination state. Please refine your destination criteria."
                )
            else:
                messages.append("No loads available for the selected criteria. Please refine your search.")

            for message in messages:
                flash(message, "info")
        else:
            flash(f"Found {len(results)} loads matching your criteria.", "info")

        # Redirect to the same page with GET method to handle pagination via URL
        # This helps in preserving search parameters in the URL
        return redirect(url_for('index',
                                origin_city=origin_city,
                                origin_state=origin_state,
                                dest_city=dest_city,
                                dest_state=dest_state,
                                type_truck=type_truck,
                                radius=radius,
                                weight=weight,
                                page=page,
                                search=1))  # Add search flag

    else:
        # Handle GET requests (including pagination)
        # Fetch search parameters from query string
        origin_city = request.args.get('origin_city', '').strip()
        origin_state = request.args.get('origin_state', '').strip()
        dest_city = request.args.get('dest_city', '').strip()
        dest_state = request.args.get('dest_state', '').strip()
        type_truck = request.args.get('type_truck', 'Dry Van').strip() or 'Dry Van'
        radius = float(request.args.get('radius', 200))
        weight = float(request.args.get('weight', 25000))
        page = request.args.get('page', 1, type=int)

        # Check if a search has been performed based on the 'search' flag
        search_flag = request.args.get('search', type=int, default=0)
        if search_flag:
            search_performed = True
            # Perform the search
            results, total, loads_in_origin_state, loads_in_dest_state = search_loads(
                type_truck, radius, weight,
                posting_data, stop_data,
                origin_city, origin_state, dest_city, dest_state,
                page, per_page
            )
        else:
            # No search has been performed; do not fetch or display results
            results = []
            total = 0
            loads_in_origin_state = False
            loads_in_dest_state = False

    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page  # Ceiling division

    # Debugging Logs
    logger.info(f"Total Records: {total}")
    logger.info(f"Per Page: {per_page}")
    logger.info(f"Total Pages: {total_pages}")
    logger.info(f"Current Page: {page}")

    # Handle edge case where page number exceeds total_pages
    if search_flag and page > total_pages and total_pages > 0:
        logger.warning(f"Requested page ({page}) exceeds total_pages ({total_pages}). Redirecting to page {total_pages}.")
        return redirect(url_for('index',
                                origin_city=origin_city,
                                origin_state=origin_state,
                                dest_city=dest_city,
                                dest_state=dest_state,
                                type_truck=type_truck,
                                radius=radius,
                                weight=weight,
                                page=total_pages,
                                search=1))  # Ensure search flag is preserved

    # Extract unique cities and states for dropdowns
    unique_origin_cities = routes['CITY_origin'].dropna().unique().tolist()
    unique_dest_cities = routes['CITY_dest'].dropna().unique().tolist()

    # Sort the city lists for better user experience
    unique_origin_cities.sort()
    unique_dest_cities.sort()

    # Get possible states for the selected origin_city
    origin_states = []
    if origin_city:
        origin_states = routes[routes['CITY_origin'].str.lower() == origin_city.lower()]['STATE_origin'].dropna().unique().tolist()
        origin_states.sort()

    # Similarly for dest_city
    dest_states = []
    if dest_city:
        dest_states = routes[routes['CITY_dest'].str.lower() == dest_city.lower()]['STATE_dest'].dropna().unique().tolist()
        dest_states.sort()

    # Prepare dashboard stats
    dashboard_stats = {
        "active_loads": posting_data['LOAD_ID'].nunique(),
        "total_pickups": stop_data[stop_data['STOP_TYPE'].str.upper() == 'P'].shape[0],
        "total_dropoffs": stop_data[stop_data['STOP_TYPE'].str.upper() == 'D'].shape[0],
        "avg_weight": posting_data['TOTAL_WEIGHT'].mean() if 'TOTAL_WEIGHT' in posting_data.columns else 0
    }

    # Render the template
    return render_template(
        'index.html',
        map_image=map_image,
        results=results,
        type_truck=type_truck,
        radius=radius,
        weight=weight,
        origin_city=origin_city,
        origin_state=origin_state,
        dest_city=dest_city,
        dest_state=dest_state,
        unique_origin_cities=unique_origin_cities,
        unique_dest_cities=unique_dest_cities,
        origin_states=origin_states,
        dest_states=dest_states,
        dashboard_stats=dashboard_stats,
        loads_in_origin_state=loads_in_origin_state,
        loads_in_dest_state=loads_in_dest_state,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        search_performed=search_performed
    )


@app.route('/dashboard')
def dashboard():
    # Transport mode distribution - Using posting_data
    transport_mode_counts = {}
    if 'TRANSPORT_MODE' in posting_data.columns:
        transport_mode_counts = posting_data['TRANSPORT_MODE'].value_counts().to_dict()
        logger.info("Transport Mode Counts: %s", transport_mode_counts)  # Debugging

    # Top pickup cities (using stop_data)
    pickup_stats = {}
    if 'STOP_TYPE' in stop_data.columns and 'CITY' in stop_data.columns:
        pickup_stats = stop_data[stop_data['STOP_TYPE'].str.upper() == 'P']['CITY'].value_counts().head(10).to_dict()
        logger.info("Top Pickup Cities: %s", pickup_stats)  # Debugging

    # Top drop-off cities (using stop_data)
    dropoff_stats = {}
    if 'STOP_TYPE' in stop_data.columns and 'CITY' in stop_data.columns:
        dropoff_stats = stop_data[stop_data['STOP_TYPE'].str.upper() == 'D']['CITY'].value_counts().head(10).to_dict()
        logger.info("Top Drop-off Cities: %s", dropoff_stats)  # Debugging

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
        logger.info("Top City Pairs with Active Routes: %s", active_routes)  # Debugging

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
        logger.info("Average Weight by Transport Mode: %s", avg_weight_by_mode)  # Debugging

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
    city = request.args.get('city', '').strip().lower()
    location_type = request.args.get('type', '').strip().lower()  # 'origin' or 'dest'
    if location_type == 'origin':
        states = routes[routes['CITY_origin'].str.lower() == city]['STATE_origin'].dropna().unique().tolist()
    else:
        states = routes[routes['CITY_dest'].str.lower() == city]['STATE_dest'].dropna().unique().tolist()
    return jsonify({'states': states})

@app.route('/get_map', methods=['GET'])
def get_map():
    load_id = request.args.get('load_id', '').strip()
    logger.info(f"Fetching map for LOAD_ID: {load_id}")

    # Ensure LOAD_ID is a string
    load_id = str(load_id)

    # Use postings_with_stops to get load details
    postings_with_stops = get_postings_with_stops(posting_data, stop_data)

    # Fetch the load details
    load_records = postings_with_stops[postings_with_stops['LOAD_ID'] == load_id].to_dict('records')
    if not load_records:
        logger.warning(f"Load ID {load_id} not found in postings_with_stops")
        return "No route found for the given Load ID", 404

    load = load_records[0]
    logger.info(f"Load data: {load}")

    # Construct stops for map generation
    stops = [
        {"City": load['Pickup_City'], "State": load['Pickup_State']},
        {"City": load['Destination_City'], "State": load['Destination_State']}
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

@app.route('/load/<load_id>', methods=['GET'])
def load_details(load_id):
    logger.info(f"Fetching details for LOAD_ID: {load_id}")

    # Ensure LOAD_ID is a string
    load_id = str(load_id)

    # Use postings_with_stops instead of posting_data
    postings_with_stops = get_postings_with_stops(posting_data, stop_data)

    # Fetch the load details
    load_records = postings_with_stops[
        postings_with_stops['LOAD_ID'] == load_id
    ].to_dict('records')
    logger.info(f"Number of records for LOAD_ID {load_id}: {len(load_records)}")

    if not load_records:
        flash(f"No load found with ID: {load_id}", "warning")
        return redirect(url_for('index'))

    load = load_records[0]
    logger.info(f"Load data: {load}")

    # Check for required keys
    required_keys = [
        'Pickup_City', 'Pickup_State',
        'Destination_City', 'Destination_State',
        'TOTAL_WEIGHT'
    ]
    missing_keys = [key for key in required_keys if key not in load]
    if missing_keys:
        logger.error(f"Missing keys in load data: {missing_keys}")
        flash(
            f"Load data is incomplete. Missing keys: {', '.join(missing_keys)}.",
            "danger"
        )
        return redirect(url_for('index'))

    # Calculate mileage
    origin = {
        'City': load['Pickup_City'],
        'State': load['Pickup_State']
    }
    destination = {
        'City': load['Destination_City'],
        'State': load['Destination_State']
    }
    mileage_info = calculate_mileage(origin, destination)
    logger.info(f"Mileage info for LOAD_ID {load_id}: {mileage_info}")

    # Parse mileage data
    if 'error' not in mileage_info:
        total_miles = float(mileage_info[0]['ReportLines'][1]['TMiles'])
        fuel_data = calculate_fuel_efficiency(
            total_miles=total_miles,
            truck_weight=load['TOTAL_WEIGHT']
        )
        mileage_info = {
            'total_miles': total_miles,
            'total_hours': mileage_info[0]['ReportLines'][1]['THours'],
            'estimated_tolls': mileage_info[0]['ReportLines'][1]['TTolls'],
            'estimated_ghg': mileage_info[0]['ReportLines'][1]['TEstghg'],
            'adjusted_efficiency': fuel_data['adjusted_efficiency'],
            'fuel_consumption': fuel_data['fuel_consumption']
        }
    else:
        logger.error(f"Mileage calculation error: {mileage_info['error']}")
        flash(f"Unable to calculate mileage: {mileage_info['error']}", "danger")
        mileage_info = None

    # Fetch coordinates for Google Maps
    pickup_coords = get_coordinates(load['Pickup_City'], load['Pickup_State'])
    destination_coords = get_coordinates(load['Destination_City'], load['Destination_State'])

    if not pickup_coords or not destination_coords:
        flash("Unable to retrieve coordinates for the specified locations.", "danger")
        return redirect(url_for('load_details', load_id=load_id))

    # Render the load_details.html template instead of directions.html
    return render_template(
        'load_details.html',  # Correct Template
        load=load,
        mileage_info=mileage_info,
        google_maps_api_key=google_maps_api_key,
        pickup_coords=pickup_coords,         # (latitude, longitude)
        destination_coords=destination_coords  # (latitude, longitude)
    )


from decimal import Decimal

def calculate_fuel_efficiency(total_miles, truck_weight, base_efficiency=Decimal('6.0')):
    """
    Calculate estimated fuel consumption (miles per gallon) based on truck load.

    :param total_miles: Total distance in miles (int, float, or Decimal).
    :param truck_weight: Weight of the truck load in pounds (int, float, or Decimal).
    :param base_efficiency: Base miles per gallon for an empty truck (Decimal).
    :return: Total fuel consumption (gallons) and adjusted miles per gallon (MPG).
    """
    # Convert inputs to Decimal
    total_miles = Decimal(total_miles)
    truck_weight = Decimal(truck_weight)

    # Validate inputs
    if total_miles <= 0:
        raise ValueError("Invalid total miles. Must be a positive number.")
    if truck_weight < 0:
        raise ValueError("Invalid truck weight. Must be a non-negative number.")
    if base_efficiency <= 0:
        raise ValueError("Invalid base efficiency. Must be a positive number.")

    # Calculate efficiency
    weight_factor = truck_weight / Decimal('1000') * Decimal('0.01')
    adjusted_efficiency = max(base_efficiency - weight_factor, Decimal('3.0'))  # Minimum MPG is 3
    fuel_consumption = total_miles / adjusted_efficiency

    return {
        'adjusted_efficiency': round(adjusted_efficiency, 2),
        'fuel_consumption': round(fuel_consumption, 2)
    }


@app.route('/directions/<load_id>', methods=['GET'])
def directions(load_id):
    logger.info(f"Fetching directions for LOAD_ID: {load_id}")

    # Ensure LOAD_ID is a string
    load_id = str(load_id)
    postings_with_stops = get_postings_with_stops(posting_data, stop_data)

    # Fetch load details
    load_records = postings_with_stops[postings_with_stops['LOAD_ID'] == load_id].to_dict('records')
    if not load_records:
        flash(f"No load found with ID: {load_id}", "warning")
        return redirect(url_for('index'))

    load = load_records[0]
    logger.info(f"Load data: {load}")

    # Fetch coordinates
    origin_coords = get_coordinates(load['Pickup_City'], load['Pickup_State'])
    destination_coords = get_coordinates(load['Destination_City'], load['Destination_State'])

    # Check coordinates
    if not origin_coords or not destination_coords:
        missing = []
        if not origin_coords:
            missing.append('origin coordinates')
        if not destination_coords:
            missing.append('destination coordinates')
        flash(f"Unable to fetch {' and '.join(missing)} for Load ID: {load_id}", "danger")
        return redirect(url_for('index'))

    # Construct stops parameter
    stops = f"{origin_coords[1]},{origin_coords[0]};{destination_coords[1]},{destination_coords[0]}"
    logger.info(f"Constructed stops parameter: {stops}")

    # Call Directions API
    directions = get_directions(stops)

    # Render 'directions.html' and pass 'load_id'
    return render_template(
        'directions.html',
        load_id=load_id,        # Pass 'load_id' directly
        directions=directions
    )

@app.route('/route/<load_id>', methods=['GET'])
def display_route(load_id):
    logger.info(f"Fetching route for LOAD_ID: {load_id}")

    # Ensure LOAD_ID is a string
    load_id = str(load_id)

    # Retrieve load details
    postings_with_stops = get_postings_with_stops(posting_data, stop_data)
    load_records = postings_with_stops[postings_with_stops['LOAD_ID'] == load_id].to_dict('records')

    if not load_records:
        flash(f"No load found with ID: {load_id}", "warning")
        return redirect(url_for('index'))

    load = load_records[0]
    logger.info(f"Load data: {load}")

    # Check for required keys
    required_keys = [
        'Pickup_City', 'Pickup_State',
        'Destination_City', 'Destination_State',
        'TOTAL_WEIGHT'
    ]
    missing_keys = [key for key in required_keys if key not in load]
    if missing_keys:
        logger.error(f"Missing keys in load data: {missing_keys}")
        flash(
            f"Load data is incomplete. Missing keys: {', '.join(missing_keys)}.",
            "danger"
        )
        return redirect(url_for('index'))

    # Fetch coordinates for pickup and destination
    pickup_coords = get_coordinates(load['Pickup_City'], load['Pickup_State'])
    destination_coords = get_coordinates(load['Destination_City'], load['Destination_State'])

    if not pickup_coords or not destination_coords:
        flash("Unable to retrieve coordinates for the specified locations.", "danger")
        return redirect(url_for('load_details', load_id=load_id))

    # Pass the necessary data to the template
    return render_template(
        'route.html',
        load=load,
        pickup_coords=pickup_coords,         # Tuple: (latitude, longitude)
        destination_coords=destination_coords,  # Tuple: (latitude, longitude)
        google_maps_api_key=google_maps_api_key
    )



if __name__ == '__main__':
    app.run(debug=True)
