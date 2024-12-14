from venv import logger
import requests
from urllib.parse import urlencode
import backoff
import json
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import os
from dotenv import load_dotenv
from utils import get_coordinates

# Load environment variables from .env file
load_dotenv()

def getHeaders(apikey):
    headers = {
        'Authorization': f'{apikey}',
        'Accept': 'application/json',
        'Content-type': 'application/json'
    }
    return headers

@backoff.on_exception(backoff.expo,
                      requests.exceptions.ReadTimeout, max_time=10)
def makeRequest(url, headers, params, postData):
    try:
        response = requests.post(url, headers=headers, params=params, data=postData, timeout=10)
        # Debugging: Log response status and content
        print(f"makeRequest Response Status Code: {response.status_code}")
        print(f"makeRequest Response Content: {response.text[:500]}")
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        raise

def mapGenerator(stop_list):
    # Create postData for the request
    postData = {
        "Map": {
            "Viewport": {"Region": 0},
            "Width": 1366,
            "Height": 768,
             "Drawers": [
                8, 11, 9, 21, 26, 13, 2, 27, 17, 22  # Detailed layers
            ],
        },
        "Routes": [
            {
                "Stops": [
                    {
                        "Address": {
                            "City": stop["City"],
                            "State": stop["State"],
                            "Zip": stop.get("Zip", ""),
                        },
                        "Region": 4,
                    }
                    for stop in stop_list
                ],
                "Options": {"HighwayOnly": True, "DistanceUnits": 0},
            }
        ],
    }

    apikey = os.getenv('PCMILER_API_KEY')
    if not apikey:
        print("Error: PCMILER_API_KEY environment variable is not set.")
        return None

    try:
        url = 'https://pcmiler.alk.com/apis/rest/v1.0/service.svc/mapRoutes?dataset=Current'
        headers = getHeaders(apikey)
        
        # Send request
        response = requests.post(url, headers=headers, data=json.dumps(postData))
        
        # Debugging: Log response details
        print(f"mapGenerator Response Status Code: {response.status_code}")
        print(f"mapGenerator Response Headers: {response.headers}")
        
        # Check Content-Type
        content_type = response.headers.get('Content-Type', '')
        print(f"mapGenerator Content-Type: {content_type}")

        if not content_type.startswith('image/'):
            print(f"Unexpected Content-Type. Response Content: {response.text[:500]}")
            return None

        # Try to open the image
        img = Image.open(BytesIO(response.content))
        print("Image successfully received and opened.")
        return img

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except UnidentifiedImageError as e:
        print(f"PIL cannot identify image file: {e}")


def calculate_mileage(origin, destination):
    """
    Calculate mileage between origin and destination using PC*MILER API.
    """
    api_key = os.getenv('PCMILER_API_KEY')
    url = 'https://pcmiler.alk.com/apis/rest/v1.0/Service.svc/route/routeReports'

    # Fetch coordinates for origin and destination
    origin_coords = get_coordinates(origin['City'], origin['State'])
    destination_coords = get_coordinates(destination['City'], destination['State'])

    if not origin_coords or not destination_coords:
        logger.error(f"Coordinates missing for origin or destination. Origin: {origin}, Destination: {destination}")
        return {'error': 'Coordinates missing for origin or destination'}

    # Construct stops parameter
    stops = f"{origin_coords[1]},{origin_coords[0]};{destination_coords[1]},{destination_coords[0]}"
    logger.info(f"Constructed stops parameter: {stops}")

    try:
        # Define API parameters
        params = {
            'stops': stops,
            'reports': 'Mileage',
            'authToken': api_key,
            'dataset': 'Current'
        }

        # Make the API request
        response = requests.get(url, params=params)
        response.raise_for_status()

        # Parse and return the API response
        mileage_data = response.json()
        logger.info(f"Successfully fetched mileage data: {mileage_data}")
        return mileage_data

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}, Response: {response.text}")
        return {'error': 'HTTP error during mileage calculation'}
    except Exception as err:
        logger.error(f"Unexpected error occurred: {err}")
        return {'error': 'Unable to fetch mileage information'}


def get_directions(stops):
    """
    Fetch turn-by-turn directions from the PCMiler Directions API.

    :param stops: A semicolon-separated string of stop coordinates (e.g., "lat1,lon1;lat2,lon2").
    :return: A list of direction steps.
    """
    api_key = os.getenv('PCMILER_API_KEY')  # PCMiler API Key
    url = 'https://pcmiler.alk.com/apis/rest/v1.0/Service.svc/route/routeReports'

    params = {
        'stops': stops,
        'reports': 'Directions',
        'authToken': api_key
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"Directions API Response: {data}")

        # Extract directions
        directions = []
        report_legs = data[0].get('ReportLegs', [])
        for leg in report_legs:
            for line in leg.get('ReportLines', []):
                direction_step = {
                    "instruction": line.get('Direction', 'No instruction provided'),
                    "distance": line.get('Dist', 'N/A'),
                    "time": line.get('Time', 'N/A'),
                    "turn_instruction": line.get('TurnInstruction', 'N/A')
                }
                directions.append(direction_step)

        return directions
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching directions: {e}")
        return [{"instruction": f"Error fetching directions: {str(e)}"}]
    except KeyError:
        logger.error("Unexpected response format from PCMiler Directions API.")
        return [{"instruction": "Unexpected response format."}]







# Additional Debug Function
def testAPI():
    """Test PCMiler API connectivity with a sample stop list."""
    stop_list = [
        {"City": "Madison", "State": "WI", "Zip": "53703"},
        {"City": "Chicago", "State": "IL", "Zip": "60601"}
    ]
    img = mapGenerator(stop_list)
    if img:
        img.show()  # Opens the image using the default viewer
    else:
        print("Failed to generate map.")
