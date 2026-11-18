/**
 * CivicSight Frontend Configuration Template
 * 
 * Copy this template to `frontend/js/config.local.js` (which is gitignored):
 *   cp frontend/js/config.example.js frontend/js/config.local.js
 * 
 * SETUP INSTRUCTIONS (Google Cloud Console):
 * 1. Project & Billing:
 *    - Create or select a Google Cloud Project with active billing enabled.
 *    - Set up a daily budget alert to avoid unexpected billing charges.
 * 2. Enable APIs:
 *    - Enable 'Maps JavaScript API' (Required for map rendering & AdvancedMarkerElement).
 *    - Enable 'Geocoding API' (Optional, used for reverse geocoding coordinates to street addresses).
 * 3. Create Map ID:
 *    - Go to Google Maps Platform > Map Management.
 *    - Create a Map ID (JavaScript / Vector or Raster). Map ID is REQUIRED for AdvancedMarkerElement.
 * 4. API Key & Security Restrictions:
 *    - Go to Google Cloud Console > APIs & Services > Credentials > Create API Key.
 *    - Set Application Restrictions: HTTP referrers (e.g., `http://localhost:*/*`, `http://127.0.0.1:*/*`, or your deployed domain).
 *    - Set API Restrictions: Restrict to 'Maps JavaScript API' and 'Geocoding API'.
 */

window.CIVICSIGHT_CONFIG = {
  // Required: Google Maps JavaScript API Key (AIza...)
  GOOGLE_MAPS_API_KEY: "YOUR_GOOGLE_MAPS_API_KEY",

  // Required: Google Maps Map ID for AdvancedMarkerElement & Cloud Styling
  GOOGLE_MAPS_MAP_ID: "YOUR_GOOGLE_MAPS_MAP_ID",

  // Optional: Configurable default center coordinates [Latitude, Longitude]
  DEFAULT_CENTER: { lat: 37.7749, lng: -122.4194 },
  DEFAULT_ZOOM: 13,
};
