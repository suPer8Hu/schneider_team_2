# precompute_coords.py

import pandas as pd
from geopy.geocoders import Nominatim
import pickle
import time

# Initialize geolocator with a unique user agent
geolocator = Nominatim(user_agent="freight_load_search_app")

def get_coordinates(city, state):
    """
    Geocode the given city and state to obtain latitude and longitude.
    """
    try:
        location = geolocator.geocode(f"{city}, {state}")
        if location:
            print(f"Coordinates for {city}, {state}: ({location.latitude}, {location.longitude})")
            return (location.latitude, location.longitude)
        else:
            print(f"Could not find coordinates for {city}, {state}")
            return None
    except Exception as e:
        print(f"Error geocoding {city}, {state}: {e}")
        return None

def main():
    """
    Main function to load CSV data, extract unique city-state combinations,
    geocode them, and save the coordinates mapping.
    """
    # Specify the correct delimiter based on your CSV files
    delimiter = ','  # Comma-separated

    # Load CSV data with the correct delimiter
    try:
        posting_data = pd.read_csv("./load_posting.csv", sep=delimiter)
        stop_data = pd.read_csv("./load_stop.csv", sep=delimiter)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    except pd.errors.ParserError as e:
        print(f"Error parsing CSV files: {e}")
        return

    # Print column names to verify
    print("Posting Data Columns:", posting_data.columns.tolist())
    print("Stop Data Columns:", stop_data.columns.tolist())

    # Check if 'CITY' and 'STATE' columns exist in stop_data
    required_columns = ['CITY', 'STATE']
    for col in required_columns:
        if col not in stop_data.columns:
            print(f"Error: Column '{col}' not found in load_stop.csv")
            return

    # Combine CITY and STATE into a single string for uniqueness with standardized formatting
    stop_data['CITY_STATE'] = stop_data.apply(
        lambda row: f"{row['CITY'].title().strip()}, {row['STATE'].upper().strip()}", axis=1
    )

    # Extract unique city-state combinations from 'load_stop.csv'
    unique_stop_cities = stop_data['CITY_STATE'].unique()

    city_coords = {}

    total_cities = len(unique_stop_cities)
    print(f"Total unique city-state combinations to process: {total_cities}")

    for idx, city_state in enumerate(unique_stop_cities, start=1):
        if pd.isnull(city_state):
            print(f"Skipping NaN CITY_STATE at index {idx}")
            continue  # Skip if CITY_STATE is NaN
        try:
            city, state = city_state.split(', ')
        except ValueError:
            print(f"Invalid CITY_STATE format: '{city_state}' at index {idx}")
            city_coords[city_state] = None
            continue
        coords = get_coordinates(city, state)
        city_coords[city_state] = coords
        time.sleep(1)  # Respect Nominatim's usage policy

    # Save the coordinates mapping to a pickle file
    try:
        with open('city_coords.pkl', 'wb') as f:
            pickle.dump(city_coords, f)
        print("City coordinates have been saved to 'city_coords.pkl'.")
    except Exception as e:
        print(f"Error saving 'city_coords.pkl': {e}")

if __name__ == "__main__":
    main()
