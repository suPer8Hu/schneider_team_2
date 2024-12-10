# precompute_coords.py

import pandas as pd
from geopy.geocoders import Nominatim
import pickle
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_coordinates(geolocator, city, state):
    """
    Geocode the given city and state to obtain latitude and longitude.
    """
    try:
        location = geolocator.geocode(f"{city}, {state}")
        if location:
            logging.info(f"Geocoded: {city}, {state} -> ({location.latitude}, {location.longitude})")
            return (location.latitude, location.longitude)
        else:
            logging.warning(f"Could not geocode: {city}, {state}")
            return None
    except Exception as e:
        logging.error(f"Error geocoding {city}, {state}: {e}")
        return None

def main():
    """
    Main function to load CSV data, extract unique city-state combinations,
    geocode them, and save the coordinates mapping.
    """
    # Initialize geolocator with a unique user agent
    geolocator = Nominatim(user_agent="freight_load_search_app")

    # Load CSV files into Pandas DataFrames
    try:
        load_posting_df = pd.read_csv("load_posting.csv")
        load_stop_df = pd.read_csv("load_stop.csv")
        logging.info("CSV files loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading CSV files: {e}")
        return

    # Combine pickup and dropoff cities and states
    pickup_cities = load_stop_df[['CITY', 'STATE']].drop_duplicates()
    dropoff_cities = load_stop_df[['CITY_DEST', 'STATE_DEST']].drop_duplicates()
    # Rename columns to standardize
    pickup_cities.columns = ['CITY', 'STATE']
    dropoff_cities.columns = ['CITY', 'STATE']
    all_cities = pd.concat([pickup_cities, dropoff_cities]).drop_duplicates()

    # Ensure consistent formatting: lowercase and strip spaces
    all_cities['CITY'] = all_cities['CITY'].str.strip().str.lower()
    all_cities['STATE'] = all_cities['STATE'].str.strip().str.lower()

    # Create a list of unique city-state strings
    all_cities['CITY_STATE'] = all_cities.apply(lambda row: f"{row['CITY']}, {row['STATE']}", axis=1)
    unique_city_states = all_cities['CITY_STATE'].unique()
    total_cities = len(unique_city_states)
    logging.info(f"Total unique city-state combinations to process: {total_cities}")

    city_coords = {}

    for idx, city_state in enumerate(unique_city_states, start=1):
        city, state = city_state.split(', ')
        coords = get_coordinates(geolocator, city, state)
        city_coords[city_state] = coords
        time.sleep(1)  # Respect Nominatim's usage policy

    # Save the coordinates mapping to a pickle file
    try:
        with open('city_coords.pkl', 'wb') as f:
            pickle.dump(city_coords, f)
        logging.info("City coordinates have been saved to 'city_coords.pkl'.")
    except Exception as e:
        logging.error(f"Error saving 'city_coords.pkl': {e}")

if __name__ == "__main__":
    main()

# import pandas as pd
# from geopy.geocoders import Nominatim
# import pickle

# # Load your datasets
# stop_data = pd.read_csv("load_stop.csv")

# # Combine pickup and dropoff cities and states
# all_cities = pd.concat([
#     stop_data[['CITY', 'STATE']]
# ]).drop_duplicates()

# # Initialize geolocator
# geolocator = Nominatim(user_agent="freight_load_search_app")

# city_coords = {}

# for index, row in all_cities.iterrows():
#     city = row['CITY']
#     state = row['STATE']
#     city_state = f"{city}, {state}"
#     location = geolocator.geocode(city_state)
#     if location:
#         city_coords[city_state.lower()] = (location.latitude, location.longitude)
#         print(f"Geocoded: {city_state}")
#     else:
#         print(f"Could not geocode: {city_state}")

# # Save the coordinates
# with open('city_coords.pkl', 'wb') as f:
#     pickle.dump(city_coords, f)
