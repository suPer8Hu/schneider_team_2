# precompute_coords.py

import pandas as pd
from geopy.geocoders import Nominatim
import pickle
import time
from pyspark.sql import SparkSession

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
    spark = SparkSession.builder.appName("FreightCoordPrecompute").getOrCreate()

    # Load CSV files into Spark DataFrames
    load_posting_df = spark.read.csv("load_posting.csv", header=True, inferSchema=True)
    load_stop_df = spark.read.csv("load_stop.csv", header=True, inferSchema=True)

    # Combine CITY and STATE for unique identification
    stop_data = load_stop_df.selectExpr("CITY", "STATE", "CONCAT(CITY, ', ', STATE) AS CITY_STATE")
    unique_stop_cities = stop_data.select("CITY_STATE").distinct().collect()

    city_coords = {}

    total_cities = len(unique_stop_cities)
    print(f"Total unique city-state combinations to process: {total_cities}")

    for idx, row in enumerate(unique_stop_cities, start=1):
        city_state = row["CITY_STATE"]
        try:
            city, state = city_state.split(', ')
            coords = get_coordinates(city, state)
            city_coords[city_state] = coords
        except ValueError:
            print(f"Invalid CITY_STATE format: '{city_state}' at index {idx}")
            city_coords[city_state] = None
            continue
        time.sleep(1)  # Respect Nominatim's usage policy

    # Save the coordinates mapping to a pickle file
    try:
        with open('city_coords.pkl', 'wb') as f:
            pickle.dump(city_coords, f)
        print("City coordinates have been saved to 'city_coords.pkl'.")
    except Exception as e:
        print(f"Error saving 'city_coords.pkl': {e}")

    spark.stop()

if __name__ == "__main__":
    main()
