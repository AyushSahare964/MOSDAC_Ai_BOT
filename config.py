# config.py

# Neo4j Database Configuration
NEO4J_URI = "neo4j://127.0.0.1:7687" # Replace if your Neo4j is elsewhere
NEO4J_USERNAME = "neo4j"           # *** IMPORTANT: Replace with your actual Neo4j username ***
NEO4J_PASSWORD = "Samyak123" # *** IMPORTANT: Replace with your actual Neo4j password ***

# --- NEW: Web Portal URLs to Scrape on MOSDAC ---
MOSDAC_BASE_URL = "https://www.mosdac.gov.in" # Base URL for MOSDAC
MOSDAC_WEB_PORTAL_URL = f"{MOSDAC_BASE_URL}/data" # Main data page (might contain links to others)

# Specific URLs found from inspecting the HTML snippet for structured lists
# These are relative paths, will be joined with MOSDAC_BASE_URL
MOSDAC_MISSIONS_MENU_PATH = "/" # The missions menu is on the homepage itself
MOSDAC_OPEN_DATA_MENU_PATH = "/" # The open data menu is on the homepage itself


# Define your Knowledge Graph Schema for MOSDAC (concepts related to satellite data)
KG_SCHEMA = {
    "nodes": [
        "DataProduct",      # e.g., "Sea Surface Temperature", "Cloud Top Pressure"
        "Satellite",        # e.g., "INSAT-3D", "Kalpana-1"
        "Sensor",           # e.g., "Imager", "Sounder"
        "Parameter",        # e.g., "Temperature", "Pressure", "Wind Speed"
        "DataFormat",       # e.g., "NetCDF", "HDF", "JPEG"
        "ApplicationArea",  # e.g., "Cyclone Forecasting", "Agricultural Monitoring", "Climate Study"
        "Service",          # e.g., "Data Download", "Visualization Tool"
        "TimeResolution",   # e.g., "Hourly", "Daily", "Monthly"
        "SpatialResolution",# e.g., "1km", "5km", "Global"
        "Institution"       # e.g., "ISRO", "IMD"
    ],
    "relationships": [
        "PROVIDES",         # DataProduct PROVIDES Parameter
        "OBSERVED_BY",      # Parameter OBSERVED_BY Sensor
        "FROM_SATELLITE",   # DataProduct FROM_SATELLITE Satellite
        "USES_SENSOR",      # Satellite USES_SENSOR Sensor
        "AVAILABLE_IN_FORMAT", # DataProduct AVAILABLE_IN_FORMAT DataFormat
        "APPLICABLE_FOR",   # DataProduct APPLICABLE_FOR ApplicationArea
        "HAS_TIME_RESOLUTION", # DataProduct HAS_TIME_RESOLUTION TimeResolution
        "HAS_SPATIAL_RESOLUTION", # DataProduct HAS_SPATIAL_RESOLUTION SpatialResolution
        "OFFERS_SERVICE",   # Institution OFFERS_SERVICE Service
        "PRODUCED_BY"       # DataProduct PRODUCED_BY Institution
    ],
    "properties": {
        "DataProduct": ["name", "description", "coverage", "update_frequency", "link"],
        "Satellite": ["name", "mission_type", "status", "launch_date", "link"], # Added 'link' property
        "Sensor": ["name", "band", "wavelength_range"],
        "Parameter": ["name", "unit"],
        "DataFormat": ["name", "description"],
        "ApplicationArea": ["name"],
        "Service": ["name", "description", "access_url"],
        "TimeResolution": ["value"], # e.g., "hourly", "daily"
        "SpatialResolution": ["value"], # e.g., "1km", "5km"
        "Institution": ["name", "type"]
    }
}
