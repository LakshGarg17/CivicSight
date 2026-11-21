/**
 * CivicSight Unified Google Maps Abstraction Module
 * 
 * Centralized loader and component wrapper for the Google Maps JavaScript API.
 * Uses current modern APIs:
 * - google.maps.importLibrary dynamic loading
 * - google.maps.marker.AdvancedMarkerElement (requires Map ID)
 * - @googlemaps/markerclusterer for marker grouping
 * - Semi-transparent Circle density view (replacing deprecated HeatmapLayer)
 * 
 * Security: API keys and Map IDs are read strictly from window.CIVICSIGHT_CONFIG
 * (configured via gitignored frontend/js/config.local.js or frontend/.env).
 * Keys are never logged, never hardcoded, and never exposed in error outputs.
 */

(function (window) {
  'use strict';

  // Configurable Defaults
  const DEFAULT_LAT = 37.7749;
  const DEFAULT_LNG = -122.4194;
  const DEFAULT_ZOOM = 13;
  const GPS_ZOOM = 17;

  // JSON Dark Mode Styling (Zero-cost native styling for Google Maps)
  const GOOGLE_MAPS_DARK_STYLES = [
    { elementType: "geometry", stylers: [{ color: "#1e242d" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#1e242d" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#8a9ba8" }] },
    { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#9ca5b3" }] },
    { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#9ca5b3" }] },
    { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#172b2c" }] },
    { featureType: "poi.park", elementType: "labels.text.fill", stylers: [{ color: "#5d8a6e" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#2c3542" }] },
    { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#1b2129" }] },
    { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#cbd5e1" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#3a4659" }] },
    { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#242d38" }] },
    { featureType: "road.highway", elementType: "labels.text.fill", stylers: [{ color: "#f1f5f9" }] },
    { featureType: "transit", elementType: "geometry", stylers: [{ color: "#242d38" }] },
    { featureType: "transit.station", elementType: "labels.text.fill", stylers: [{ color: "#9ca5b3" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#0f172a" }] },
    { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#475569" }] },
    { featureType: "water", elementType: "labels.text.stroke", stylers: [{ color: "#0f172a" }] }
  ];

  let loadPromise = null;
  let hasLoggedConfigWarning = false;
  let hasAuthFailed = false;

  // Global Google Maps Authentication Failure Hook (Mandatory graceful failure)
  window.gm_authFailure = function () {
    hasAuthFailed = true;
    console.warn("CivicSightMap: Google Maps authentication failure (gm_authFailure). Check API key validity, billing status, API enablement, or HTTP referrer restrictions.");
    document.querySelectorAll('.report-map, .dashboard-map-canvas, .readonly-map-canvas').forEach(container => {
      CivicSightMap.renderFallback(
        container,
        "Google Maps Authorization Failed",
        "The Google Maps API key was rejected. Verify in Google Cloud Console that billing is active, 'Maps JavaScript API' is enabled, and HTTP referrer restrictions match this origin."
      );
    });
  };

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Retrieves configuration from window.CIVICSIGHT_CONFIG (populated via config.local.js)
   */
  async function resolveConfig() {
    const cfg = window.CIVICSIGHT_CONFIG || {};
    const apiKey = (cfg.GOOGLE_MAPS_API_KEY || cfg.VITE_GOOGLE_MAPS_API_KEY || "").trim();
    const mapId = (cfg.GOOGLE_MAPS_MAP_ID || cfg.VITE_GOOGLE_MAPS_MAP_ID || "").trim();

    return {
      apiKey: apiKey,
      mapId: mapId,
      defaultCenter: cfg.DEFAULT_CENTER || { lat: DEFAULT_LAT, lng: DEFAULT_LNG },
      defaultZoom: cfg.DEFAULT_ZOOM || DEFAULT_ZOOM,
      isConfigured: Boolean(
        apiKey &&
        !apiKey.startsWith("YOUR_") &&
        !apiKey.startsWith("replace-") &&
        mapId &&
        !mapId.startsWith("YOUR_")
      )
    };
  }

  /**
   * Loads Google Maps JS API asynchronously via dynamic loader (ONCE per session)
   */
  async function loadGoogleMaps() {
    if (loadPromise) return loadPromise;

    loadPromise = (async () => {
      const config = await resolveConfig();

      if (!config.isConfigured) {
        hasLoggedConfigWarning = true;
        return { available: false, reason: "unconfigured", config };
      }

      // Bootstrap official dynamic loader if not already present
      if (!window.google || !window.google.maps) {
        try {
          await new Promise((resolve, reject) => {
            const existing = document.querySelector('script[data-civicsight-gmaps="true"]');
            if (existing) {
              existing.addEventListener("load", () => resolve(), { once: true });
              existing.addEventListener("error", () => reject(new Error("Google Maps script load failed")), { once: true });
              return;
            }
            const script = document.createElement("script");
            script.dataset.civicsightGmaps = "true";
            script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(config.apiKey)}&v=weekly&loading=async`;
            script.async = true;
            script.defer = true;
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Google Maps script load failed"));
            document.head.appendChild(script);
          });
        } catch (err) {
          return { available: false, reason: "script_load_failed", error: err, config };
        }
      }

      try {
        const { Map, InfoWindow, Circle } = await google.maps.importLibrary("maps");
        const { AdvancedMarkerElement, PinElement } = await google.maps.importLibrary("marker");
        let geocoderLib = null;
        try {
          geocoderLib = await google.maps.importLibrary("geocoding");
        } catch (_) { }

        return {
          available: true,
          google: window.google,
          config: config,
          classes: {
            Map,
            InfoWindow,
            Circle,
            AdvancedMarkerElement,
            PinElement,
            Geocoder: geocoderLib ? geocoderLib.Geocoder : null
          }
        };
      } catch (err) {
        return { available: false, reason: "library_import_failed", error: err, config };
      }
    })();

    return loadPromise;
  }

  /**
   * Helper to create custom priority-colored AdvancedMarker DOM elements
   */
  function createSeverityPinElement(priority) {
    const norm = (priority || "").toUpperCase();
    let pinColor = "var(--color-warning, #d97706)"; // Medium amber
    if (norm === "HIGH") pinColor = "var(--color-danger, #dc2626)"; // High red
    else if (norm === "LOW") pinColor = "var(--color-success, #16a34a)"; // Low green

    const container = document.createElement("div");
    container.className = `gm-severity-pin gm-pin-${norm.toLowerCase()}`;
    container.innerHTML = `
      <svg class="severity-pin-svg" width="32" height="40" viewBox="0 0 34 42" fill="none">
        <path d="M17 41C17 41 31 25.5 31 16C31 7.71573 24.732 1 17 1C9.26801 1 3 7.71573 3 16C3 25.5 17 41 17 41Z" fill="${pinColor}" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round"/>
        <circle cx="17" cy="15" r="5.5" fill="#ffffff"/>
      </svg>
    `;
    return container;
  }

  /**
   * Helper to render non-blocking graceful fallback overlay inside any map element
   */
  function renderFallback(container, title, message) {
    if (!container) return;
    container.innerHTML = `
      <div class="map-fallback-overlay" role="alert">
        <div class="map-fallback-card">
          <div class="map-fallback-icon">🗺️</div>
          <h4 class="map-fallback-title">${title}</h4>
          <p class="map-fallback-desc">${message}</p>
          <span class="map-fallback-hint">GPS coordinates and reporting workflows remain fully functional.</span>
        </div>
      </div>
    `;
  }

  // In-memory Reverse Geocoding Cache
  const reverseGeocodeCache = new Map();
  let lastGeocodeRequestTime = 0;

  /**
   * Public API
   */
  const CivicSightMap = {
    load: loadGoogleMaps,
    renderFallback: renderFallback,

    /**
     * Initializes the Citizen Incident Reporting Map
     */
    async createReportingMap(containerId, options = {}) {
      const container = typeof containerId === "string" ? document.getElementById(containerId) : containerId;
      if (!container) return null;

      const initialLat = options.initialLat || DEFAULT_LAT;
      const initialLng = options.initialLng || DEFAULT_LNG;
      const onLocationChange = options.onLocationChange || (() => { });

      const loaded = await loadGoogleMaps();

      if (!loaded.available) {
        const isUnconfigured = loaded.reason === "unconfigured";
        const title = isUnconfigured ? "Map unavailable: API key not configured" : "Map service unavailable";
        const msg = isUnconfigured
          ? "Set GOOGLE_MAPS_API_KEY and GOOGLE_MAPS_MAP_ID in frontend/js/config.local.js to enable the interactive map."
          : "Google Maps could not be initialized. You can still submit reports using manual or GPS coordinates.";
        renderFallback(container, title, msg);

        return {
          isAvailable: false,
          setPosition: () => { },
          setAccuracy: () => { },
          clearAccuracy: () => { },
          reverseGeocode: async () => null,
        };
      }

      const { Map, Circle } = loaded.classes;
      const { AdvancedMarkerElement } = loaded.classes;
      const config = loaded.config;

      const isDark = document.documentElement.getAttribute("data-theme") === "dark";

      const map = new Map(container, {
        center: { lat: initialLat, lng: initialLng },
        zoom: GPS_ZOOM,
        mapId: config.mapId,
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        styles: isDark ? GOOGLE_MAPS_DARK_STYLES : [],
      });

      // Update map styles when theme changes
      const themeObserver = new MutationObserver(() => {
        const nextDark = document.documentElement.getAttribute("data-theme") === "dark";
        map.setOptions({ styles: nextDark ? GOOGLE_MAPS_DARK_STYLES : [] });
      });
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

      // Create draggable AdvancedMarkerElement
      const marker = new AdvancedMarkerElement({
        map: map,
        position: { lat: initialLat, lng: initialLng },
        gmpDraggable: true,
        title: "Drag to pinpoint hazard location",
      });

      let accuracyCircle = null;

      // Marker drag event
      marker.addListener("dragend", () => {
        const pos = marker.position;
        const lat = typeof pos.lat === "function" ? pos.lat() : pos.lat;
        const lng = typeof pos.lng === "function" ? pos.lng() : pos.lng;
        if (accuracyCircle) {
          accuracyCircle.setMap(null);
          accuracyCircle = null;
        }
        onLocationChange(lat, lng, "manual_drag");
      });

      // Map click event
      map.addListener("click", (e) => {
        const lat = e.latLng.lat();
        const lng = e.latLng.lng();
        marker.position = { lat, lng };
        if (accuracyCircle) {
          accuracyCircle.setMap(null);
          accuracyCircle = null;
        }
        onLocationChange(lat, lng, "map_click");
      });

      return {
        isAvailable: true,
        map: map,
        marker: marker,

        setPosition(lat, lng, zoom = GPS_ZOOM) {
          marker.position = { lat, lng };
          map.setCenter({ lat, lng });
          if (zoom) map.setZoom(zoom);
        },

        setAccuracy(lat, lng, radius) {
          if (accuracyCircle) accuracyCircle.setMap(null);
          if (radius > 0) {
            accuracyCircle = new Circle({
              map: map,
              center: { lat, lng },
              radius: radius,
              fillColor: "#0284c7",
              fillOpacity: 0.15,
              strokeColor: "#0284c7",
              strokeOpacity: 0.8,
              strokeWeight: 1.5,
            });
          }
        },

        clearAccuracy() {
          if (accuracyCircle) {
            accuracyCircle.setMap(null);
            accuracyCircle = null;
          }
        },

        async reverseGeocode(lat, lng) {
          const roundedLat = parseFloat(lat.toFixed(4));
          const roundedLng = parseFloat(lng.toFixed(4));
          const cacheKey = `${roundedLat},${roundedLng}`;

          if (reverseGeocodeCache.has(cacheKey)) {
            return reverseGeocodeCache.get(cacheKey);
          }

          if (!loaded.classes.Geocoder) return null;

          // Rate limit: at most 1 request per second
          const now = Date.now();
          const elapsed = now - lastGeocodeRequestTime;
          if (elapsed < 1000) {
            await new Promise(r => setTimeout(r, 1000 - elapsed));
          }
          lastGeocodeRequestTime = Date.now();

          const geocoder = new loaded.classes.Geocoder();

          return new Promise((resolve) => {
            geocoder.geocode({ location: { lat, lng } }, (results, status) => {
              if (status === "OK" && results && results[0]) {
                const formatted = results[0].formatted_address;
                reverseGeocodeCache.set(cacheKey, formatted);
                resolve(formatted);
              } else {
                console.warn(`CivicSightMap: Geocoder response '${status}' for coords (${lat}, ${lng})`);
                resolve(null);
              }
            });
          });
        }
      };
    },

    /**
     * Initializes the Municipal Operations Center Hazard Map
     */
    async createHazardMap(containerId, options = {}) {
      const container = typeof containerId === "string" ? document.getElementById(containerId) : containerId;
      if (!container) return null;

      const loaded = await loadGoogleMaps();

      if (!loaded.available) {
        const isUnconfigured = loaded.reason === "unconfigured";
        const title = isUnconfigured ? "Hazard Map Unavailable: API Key Not Configured" : "Hazard Map Unavailable";
        const msg = isUnconfigured
          ? "Set GOOGLE_MAPS_API_KEY and GOOGLE_MAPS_MAP_ID in frontend/js/config.local.js to activate the municipal geospatial hazard map."
          : "Google Maps service could not be loaded. Triage queue and report management remain fully accessible in the table below.";
        renderFallback(container, title, msg);
        return {
          isAvailable: false,
          updateReports: () => { },
          setMode: () => { }
        };
      }

      const { Map, InfoWindow, Circle } = loaded.classes;
      const { AdvancedMarkerElement } = loaded.classes;
      const config = loaded.config;

      const isDark = document.documentElement.getAttribute("data-theme") === "dark";

      const map = new Map(container, {
        center: config.defaultCenter,
        zoom: config.defaultZoom,
        mapId: config.mapId,
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        styles: isDark ? GOOGLE_MAPS_DARK_STYLES : [],
      });

      const themeObserver = new MutationObserver(() => {
        const nextDark = document.documentElement.getAttribute("data-theme") === "dark";
        map.setOptions({ styles: nextDark ? GOOGLE_MAPS_DARK_STYLES : [] });
      });
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

      let currentMarkers = [];
      let highPriorityMarkers = [];
      let medLowMarkers = [];
      let densityCircles = [];
      let clustererInstance = null;
      let activeMode = "standard"; // "standard" | "cluster" | "heat"
      const infoWindow = new InfoWindow();

      function clearMapOverlays() {
        currentMarkers.forEach(m => m.map = null);
        highPriorityMarkers.forEach(m => m.map = null);
        medLowMarkers.forEach(m => m.map = null);
        densityCircles.forEach(c => c.setMap(null));
        if (clustererInstance) {
          clustererInstance.clearMarkers();
        }
        currentMarkers = [];
        highPriorityMarkers = [];
        medLowMarkers = [];
        densityCircles = [];
      }

      function applyMode() {
        // 1. Reset visibility
        currentMarkers.forEach(m => m.map = null);
        densityCircles.forEach(c => c.setMap(null));
        if (clustererInstance) clustererInstance.clearMarkers();

        if (activeMode === "cluster") {
          // Clustering: Medium and Low markers clustered; High-priority NEVER hidden
          if (window.markerClusterer && window.markerClusterer.MarkerClusterer) {
            if (!clustererInstance) {
              clustererInstance = new window.markerClusterer.MarkerClusterer({ map });
            }
            clustererInstance.addMarkers(medLowMarkers);
          } else {
            medLowMarkers.forEach(m => m.map = map);
          }
          // High-priority reports stay permanently unclustered and visible
          highPriorityMarkers.forEach(m => m.map = map);

        } else if (activeMode === "heat") {
          // Density view: show semi-transparent circles + keep high-priority pins visible
          densityCircles.forEach(c => c.setMap(map));
          highPriorityMarkers.forEach(m => m.map = map);

        } else {
          // Standard: all individual pins visible
          currentMarkers.forEach(m => m.map = map);
        }
      }

      return {
        isAvailable: true,
        map: map,

        setMode(mode) {
          activeMode = mode;
          applyMode();
        },

        updateReports(reports = [], onInspect) {
          clearMapOverlays();

          const bounds = new google.maps.LatLngBounds();
          let validCount = 0;

          reports.forEach((report) => {
            if (typeof report.latitude !== "number" || typeof report.longitude !== "number") return;

            const pos = { lat: report.latitude, lng: report.longitude };
            const priority = (report.priority || "MEDIUM").toUpperCase();
            const severity = report.severity || "N/A";
            const damageCode = report.damage_type || "D40";

            bounds.extend(pos);
            validCount++;

            // Create AdvancedMarkerElement
            const marker = new AdvancedMarkerElement({
              position: pos,
              title: `Report #${report.id} - ${priority} Priority`,
              content: createSeverityPinElement(priority),
              zIndex: priority === "HIGH" ? 1000 : 100,
            });

            const popupHtml = `
              <div class="dashboard-popup">
                <div class="popup-header">
                  <span class="popup-report-id">Report #${report.id}</span>
                  <span class="ml-severity-badge severity-${priority.toLowerCase()}">
                    <span class="severity-bullet"></span>
                    ${priority}
                  </span>
                </div>
                <div class="popup-meta-row">
                  <span class="popup-meta-label">Severity:</span>
                  <span class="popup-meta-val" style="font-weight: 600;">${escapeHtml(severity)}</span>
                </div>
                <div class="popup-meta-row">
                  <span class="popup-meta-label">Defect Type:</span>
                  <span class="popup-meta-val">${escapeHtml(damageCode)} Pothole/Crack</span>
                </div>
                <div class="popup-meta-row">
                  <span class="popup-meta-label">Address / Spot:</span>
                  <span class="popup-meta-val">${escapeHtml(report.address_text) || "Pinned Location"}</span>
                </div>
                <div class="popup-meta-row">
                  <span class="popup-meta-label">Status:</span>
                  <span class="popup-meta-val">${escapeHtml((report.status || "submitted").replace(/_/g, " ").toUpperCase())}</span>
                </div>
                <div class="popup-actions" style="margin-top: 0.75rem;">
                  <button type="button" class="btn btn-secondary btn-sm gm-inspect-btn" data-report-id="${report.id}" style="width: 100%;">
                    View Report
                  </button>
                </div>
              </div>
            `;

            marker.addListener("click", () => {
              infoWindow.setContent(popupHtml);
              infoWindow.open({
                anchor: marker,
                map: map,
              });

              // Attach View Report action
              setTimeout(() => {
                const btn = document.querySelector(`.gm-inspect-btn[data-report-id="${report.id}"]`);
                if (btn && onInspect) {
                  btn.onclick = () => {
                    infoWindow.close();
                    onInspect(report.id);
                  };
                }
              }, 50);
            });

            currentMarkers.push(marker);

            if (priority === "HIGH") {
              highPriorityMarkers.push(marker);
            } else {
              medLowMarkers.push(marker);
            }

            // Density Circle overlay
            const circleColor = priority === "HIGH" ? "#dc2626" : (priority === "MEDIUM" ? "#d97706" : "#16a34a");
            const circleRadius = priority === "HIGH" ? 65 : (priority === "MEDIUM" ? 45 : 30);
            const circleOpacity = priority === "HIGH" ? 0.35 : (priority === "MEDIUM" ? 0.25 : 0.18);

            const densityCircle = new Circle({
              center: pos,
              radius: circleRadius,
              fillColor: circleColor,
              fillOpacity: circleOpacity,
              strokeColor: circleColor,
              strokeOpacity: 0.6,
              strokeWeight: 1,
            });
            densityCircles.push(densityCircle);
          });

          applyMode();

          if (validCount > 0) {
            map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
            // Prevent excessive zoom on 1 report
            google.maps.event.addListenerOnce(map, "bounds_changed", () => {
              if (map.getZoom() > 16) map.setZoom(16);
            });
          }
        }
      };
    },

    /**
     * Initializes a compact Read-Only Map for Report Details and Maintenance Portals
     */
    async createReadOnlyMap(containerId, options = {}) {
      const container = typeof containerId === "string" ? document.getElementById(containerId) : containerId;
      if (!container) return null;

      const lat = options.lat || DEFAULT_LAT;
      const lng = options.lng || DEFAULT_LNG;
      const priority = options.priority || "MEDIUM";

      const loaded = await loadGoogleMaps();
      if (!loaded.available) {
        renderFallback(container, "Map unavailable", "Check configuration in frontend/js/config.local.js");
        return null;
      }

      const { Map } = loaded.classes;
      const { AdvancedMarkerElement } = loaded.classes;
      const config = loaded.config;
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";

      const map = new Map(container, {
        center: { lat, lng },
        zoom: 16,
        mapId: config.mapId,
        disableDefaultUI: true,
        zoomControl: true,
        styles: isDark ? GOOGLE_MAPS_DARK_STYLES : [],
      });

      new AdvancedMarkerElement({
        map: map,
        position: { lat, lng },
        title: `Report Location (${priority})`,
        content: createSeverityPinElement(priority),
      });

      return map;
    }
  };

  window.CivicSightMap = CivicSightMap;

})(window);
