# Project Title: Schneider Freight Load Search

## Repository Link
[GitHub Repository](https://github.com/saarthakaggarwal/schneider_team_2.git)

---

## Set-up Steps

### Prerequisites
- Python 3.9 or above
- Git
- AWS CLI configured with proper credentials
- Flask installed
- Required Python libraries (listed in `requirements.txt`)

### Steps to Set Up the Project Locally

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/saarthakaggarwal/schneider_team_2.git
   cd schneider_team_2
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate    # Windows
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**:
   - Create a `.env` file in the root directory with the following content:
     ```plaintext
     SECRET_KEY=your_secret_key_here
     GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
     AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
     AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
     ```

5. **Run the Application**:
   ```bash
   python3 app.py
   ```

6. **Access the Application**:
   Open your browser and navigate to:
   [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Overview of How the Code Works

This project provides a web-based application for searching freight loads, designed to integrate with Schneider’s FreightPower system.

### Key Features
1. **Data Handling**:
   - Loads data from AWS DynamoDB tables (`load_posting` and `load_stop`).
   - Processes and structures data into pandas DataFrames for efficient querying.

2. **Search Functionality**:
   - Allows users to filter loads based on origin, destination, radius, weight, and transport type.
   - Provides pagination for search results.

3. **Route Visualization**:
   - Uses Google Maps API to display pickup and delivery routes for selected loads.

4. **Dashboard**:
   - Provides insights into active loads, top pickup/destination locations, and average load weights.

5. **Interactive Features**:
   - Users can dynamically adjust search parameters and view alternate route suggestions.

### Code Structure
- `app.py`: Main Flask application containing routes, data handling, and API integrations.
- `utils.py`: Helper functions for geolocation and data processing.
- `templates/`: HTML templates for rendering the web interface.
- `static/`: Static assets (CSS, JS, images).
- `requirements.txt`: Python dependencies.

---

## What Works & What Doesn’t

### What Works
- **Data Integration**:
  - Successfully retrieves and processes data from AWS DynamoDB.
- **Search Functionality**:
  - Filtering by origin, destination, weight, and transport type is operational.
- **Google Maps Integration**:
  - Displays accurate routes for pickup and delivery locations.
- **Dashboard Metrics**:
  - Provides useful insights on active loads and locations.

### What Doesn’t Work
- **Radius-Based Filtering**:
  - Occasionally fails if coordinates for cities are missing or incorrect.
- **Error Handling**:
  - Limited handling of AWS connection issues or invalid user input.
- **Performance**:
  - Slower response times for large datasets due to repeated DataFrame operations.

---

## What Would You Work on Next

1. **Enhance Error Handling**:
   - Improve handling for missing or invalid data in DynamoDB.
   - Add user-friendly error messages for API and data processing errors.

2. **Optimize Performance**:
   - Cache frequently accessed data.
   - Use more efficient database queries and avoid excessive DataFrame operations.

3. **Expand Features**:
   - Allow users to upload custom load data via CSV.
   - Integrate with other Schneider systems for real-time updates.

4. **Deployment**:
   - Deploy the application on AWS using a WSGI server (e.g., Gunicorn) for production use.

5. **Testing**:
   - Add comprehensive unit and integration tests.
   - Set up CI/CD pipelines for automated testing and deployment.

---

## Additional Notes
For any questions or issues, please reach out via the repository's issue tracker.

