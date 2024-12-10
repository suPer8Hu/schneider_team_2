import pickle
import sys
from venv import logger
from geopy.geocoders import Nominatim
from cachetools import LRUCache, cached

# Load precomputed city coordinates
# Load precomputed city coordinates
try:
    with open('city_coords.pkl', 'rb') as f:
        city_coords = pickle.load(f)
    logger.info(f"Loaded {len(city_coords)} city coordinates from city_coords.pkl")
except FileNotFoundError:
    logger.error("Error: 'city_coords.pkl' not found. Please run 'precompute_coords.py' first.")
    sys.exit(1)

# Initialize geolocator
geolocator = Nominatim(user_agent="freight_load_search_app")

# Initialize an LRU cache for coordinates
coordinate_cache = LRUCache(maxsize=10000)


@cached(coordinate_cache)
def get_coordinates(city, state):
    """Retrieve coordinates for the given city and state."""
    city_state = f"{city}, {state}"
    if city_state in city_coords:
        return city_coords[city_state]
    else:
        try:
            location = geolocator.geocode(city_state, timeout=10)
            if location:
                coords = (location.latitude, location.longitude)
                city_coords[city_state] = coords
                # Optionally, save updated coordinates to 'city_coords.pkl'
                with open('city_coords.pkl', 'wb') as f:
                    pickle.dump(city_coords, f)
                return coords
            else:
                logger.warning(f"Could not find coordinates for {city_state}")
                return None
        except Exception as e:
            logger.error(f"Geocoding error for {city_state}: {e}")
            return None
