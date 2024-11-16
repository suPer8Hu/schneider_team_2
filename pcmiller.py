

import requests
from urllib.parse import urlencode
import backoff
import json
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import os
from dotenv import load_dotenv

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
            "Drawers": [8, 2, 7, 17, 15],
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
