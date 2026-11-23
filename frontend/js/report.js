/**
 * CivicSight — Report Road Damage Module 
 *
 * Implements full end-to-end citizen reporting workflow:
 * - Photo drag-and-drop file upload with live preview
 * - Interactive Google Maps with draggable pinpoint marker
 * - Browser Geolocation with robust manual click-to-pin fallback
 * - Real-time form coordinate synchronization
 * - Multipart/form-data API submission to backend with visual states (submitting, success, error)
 * - Strict theme conformity (zero hardcoded colors, CSS variables only)
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements - Image Upload
  const uploadDropzone = document.getElementById('uploadDropzone');
  const damageImageInput = document.getElementById('damageImage');
  const dropzoneIdle = document.getElementById('dropzoneIdle');
  const previewContainer = document.getElementById('previewContainer');
  const imagePreview = document.getElementById('imagePreview');
  const previewFilename = document.getElementById('previewFilename');
  const previewFilesize = document.getElementById('previewFilesize');
  const removeImageBtn = document.getElementById('removeImageBtn');
  const imageInputError = document.getElementById('imageInputError');

  // DOM Elements - Form Fields
  const roadDamageForm = document.getElementById('roadDamageForm');
  const damageDescription = document.getElementById('damageDescription');
  const descriptionError = document.getElementById('descriptionError');
  const addressTextInput = document.getElementById('addressText');
  const latitudeInput = document.getElementById('latitude');
  const longitudeInput = document.getElementById('longitude');
  const latitudeError = document.getElementById('latitudeError');
  const longitudeError = document.getElementById('longitudeError');
  const submitReportBtn = document.getElementById('submitReportBtn');
  const resetFormBtn = document.getElementById('resetFormBtn');

  // DOM Elements - Map & Status
  const recenterGpsBtn = document.getElementById('recenterGpsBtn');
  const locationStatusText = document.getElementById('locationStatusText');
  const locationStatusBadge = document.getElementById('locationStatusBadge');
  const submissionStatus = document.getElementById('submissionStatus');
  const toastContainer = document.getElementById('toastContainer');

  const DEFAULT_COORDS = [37.7749, -122.4194]; // Default San Francisco Civic Center coordinates
  const DEFAULT_ZOOM = 13;
  const GPS_ZOOM = 17;

  // Unified Google Map State
  let mapInstance = null;
  let userEditedAddressManually = false;
  let reverseGeocodeTimer = null;

  // --- 1. Toast Notification System ---
  function showToast(message, type = 'info') {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    
    let iconColor = 'var(--accent-color)';
    if (type === 'success') iconColor = 'var(--color-success)';
    if (type === 'error') iconColor = 'var(--color-danger)';

    toast.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: ${iconColor};">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
      <span>${message}</span>
    `;

    toastContainer.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- 2. Interactive Google Maps Initialization ---
  async function initMap() {
    const mapElement = document.getElementById('reportMap');
    if (!mapElement) return;

    if (typeof CivicSightMap !== 'undefined') {
      mapInstance = await CivicSightMap.createReportingMap('reportMap', {
        initialLat: DEFAULT_COORDS[0],
        initialLng: DEFAULT_COORDS[1],
        onLocationChange: (lat, lng, source) => {
          syncCoordinates(lat, lng, source === 'map_click' ? 'Map Location Selected' : 'Manual Pin Adjusted');
          scheduleReverseGeocode(lat, lng);
        }
      });
    }

    // Automatically detect location from browser on page load
    requestBrowserGeolocation(false);
  }

  // --- 3. Browser Geolocation Handler ---
  const locationLottieSlot = document.getElementById('locationLottieSlot');

  function requestBrowserGeolocation(isExplicitRetry = false) {
    if (window.isSecureContext === false) {
      updateLocationStatus('Insecure context (Click map to pin)', false, false);
      showToast('Automatic geolocation requires a secure context (HTTPS or localhost). Please click the map or enter coordinates manually.', 'warning');
      syncCoordinates(DEFAULT_COORDS[0], DEFAULT_COORDS[1], 'Default Coordinate');
      return;
    }

    if (!navigator.geolocation) {
      updateLocationStatus('Geolocation not supported (Click map to pin)', false, false);
      showToast('Geolocation is not supported by your browser. Please click the map or enter coordinates manually.', 'info');
      syncCoordinates(DEFAULT_COORDS[0], DEFAULT_COORDS[1], 'Default Coordinate');
      return;
    }

    updateLocationStatus('Finding location...', false, true);

    const geoOptions = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    };

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const userLat = position.coords.latitude;
        const userLng = position.coords.longitude;
        const accuracy = Math.round(position.coords.accuracy || 0);

        if (mapInstance && mapInstance.isAvailable) {
          mapInstance.setPosition(userLat, userLng, GPS_ZOOM);
          mapInstance.setAccuracy(userLat, userLng, accuracy);
        }

        if (accuracy > 100) {
          updateLocationStatus(`Location accuracy is low (±${accuracy}m). Drag the pin to the exact spot.`, true, false);
          showToast(`Location accuracy is low (±${accuracy}m). Drag the pin to the exact spot.`, 'info');
        } else {
          updateLocationStatus(`GPS Active (±${accuracy}m accuracy)`, true, false);
          showToast('Browser location detected automatically.', 'success');
        }

        syncCoordinates(userLat, userLng, 'GPS Location');
        scheduleReverseGeocode(userLat, userLng);
      },
      (error) => {
        let reason = 'Position Unavailable';
        let toastMsg = 'Location unavailable. You can click anywhere on the map or type coordinates.';
        
        if (error.code === 1) {
          reason = 'Permission Denied';
          toastMsg = 'Location permission denied. Click anywhere on the map or type coordinates.';
        } else if (error.code === 2) {
          reason = 'Position Unavailable';
          toastMsg = 'Location position unavailable. Click anywhere on the map or type coordinates.';
        } else if (error.code === 3) {
          reason = 'Timeout';
          toastMsg = 'Location request timed out. Please click on the map or retry.';
        }

        console.warn(`Geolocation fallback triggered: ${reason} (code ${error.code}: ${error.message})`);
        updateLocationStatus(`GPS ${reason} (Click or drag pin on map)`, false, false);
        
        // Ensure default coordinates populate so form remains fully usable
        syncCoordinates(DEFAULT_COORDS[0], DEFAULT_COORDS[1], 'Default Location');
        if (isExplicitRetry || error.code === 1) {
          showToast(toastMsg, 'info');
        }
      },
      geoOptions
    );
  }

  function updateLocationStatus(text, isActive, isLoading = false) {
    if (locationStatusText) locationStatusText.textContent = text;
    
    // Geolocation Lottie Animation slot
    if (locationLottieSlot) {
      if (isLoading) {
        locationLottieSlot.innerHTML = `<lottie-player src="../assets/lottie/locating.json" background="transparent" speed="1" loop autoplay aria-hidden="true" style="width: 24px; height: 24px;"></lottie-player>`;
        locationLottieSlot.style.display = 'inline-flex';
      } else {
        locationLottieSlot.innerHTML = '';
        locationLottieSlot.style.display = 'none';
      }
    }

    const dot = locationStatusBadge?.querySelector('.status-indicator-dot');
    if (dot) {
      if (isLoading) {
        dot.style.display = 'none';
      } else {
        dot.style.display = 'inline-block';
        if (isActive) {
          dot.classList.add('active');
        } else {
          dot.classList.remove('active');
        }
      }
    }
  }

  function syncCoordinates(lat, lng, sourceInfo) {
    const latFixed = parseFloat(lat.toFixed(6));
    const lngFixed = parseFloat(lng.toFixed(6));

    if (latitudeInput) latitudeInput.value = latFixed;
    if (longitudeInput) longitudeInput.value = lngFixed;

    // Clear coordinate validation errors if any
    if (latitudeError) latitudeError.textContent = '';
    if (longitudeError) longitudeError.textContent = '';
    latitudeInput?.classList.remove('input-invalid');
    longitudeInput?.classList.remove('input-invalid');
  }

  // Track if user manually edits address text
  if (addressTextInput) {
    addressTextInput.addEventListener('input', () => {
      userEditedAddressManually = true;
    });
  }

  // Reverse Geocoding with Google Geocoder (Debounced 800ms, cached, non-blocking)
  function scheduleReverseGeocode(lat, lng) {
    if (reverseGeocodeTimer) {
      clearTimeout(reverseGeocodeTimer);
      reverseGeocodeTimer = null;
    }
    reverseGeocodeTimer = setTimeout(async () => {
      if (!addressTextInput || userEditedAddressManually) return;
      if (mapInstance && mapInstance.reverseGeocode) {
        try {
          const address = await mapInstance.reverseGeocode(lat, lng);
          if (address && (!userEditedAddressManually || !addressTextInput.value.trim())) {
            addressTextInput.value = address;
          }
        } catch (_) {
          // Failure never blocks reporting
        }
      }
    }, 800);
  }

  // Recenter GPS Button click
  if (recenterGpsBtn) {
    recenterGpsBtn.addEventListener('click', () => {
      userEditedAddressManually = false;
      requestBrowserGeolocation(true);
    });
  }

  // Synchronize manual coordinate text input edits with map marker
  function handleManualCoordChange() {
    const latVal = parseFloat(latitudeInput.value);
    const lonVal = parseFloat(longitudeInput.value);
    if (!isNaN(latVal) && !isNaN(lonVal) && latVal >= -90 && latVal <= 90 && lonVal >= -180 && lonVal <= 180) {
      if (mapInstance && mapInstance.isAvailable) {
        mapInstance.setPosition(latVal, lonVal);
        mapInstance.clearAccuracy();
        scheduleReverseGeocode(latVal, lonVal);
      }
    }
  }

  latitudeInput?.addEventListener('change', handleManualCoordChange);
  longitudeInput?.addEventListener('change', handleManualCoordChange);

  // --- 4. Photo Selection & Real-Time ML Inference Handler ---
  let activeInferenceRequestId = 0;
  let selectedImageFile = null;
  let selectedImageDataUri = null;
  let isAnalysisConfirmed = false;

  const aiDamageResultsSection = document.getElementById('aiDamageResultsSection');
  const confirmDescriptionBtn = document.getElementById('confirmDescriptionBtn');
  const mlScanningState = document.getElementById('mlScanningState');
  const mlDetectionResultsSlot = document.getElementById('mlDetectionResultsSlot');

  function invalidateAnalysis() {
    activeInferenceRequestId++;
    isAnalysisConfirmed = false;
    if (aiDamageResultsSection) aiDamageResultsSection.style.display = 'none';
    if (mlScanningState) mlScanningState.style.display = 'none';
    if (mlDetectionResultsSlot) mlDetectionResultsSlot.innerHTML = '';
  }

  async function triggerImageInference(file, dataUri) {
    if (!file || !dataUri) return;
    const requestId = ++activeInferenceRequestId;
    const apiBase = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';

    if (aiDamageResultsSection) aiDamageResultsSection.style.display = 'block';
    if (mlScanningState) mlScanningState.style.display = 'flex';
    if (typeof CivicSightMLViewer !== 'undefined' && mlDetectionResultsSlot) {
      CivicSightMLViewer.render(mlDetectionResultsSlot, {
        imageUrl: dataUri,
        mlStatus: 'ML_PENDING',
      });
    }

    try {
      const formData = new FormData();
      formData.append('image', file);

      const detectHeaders = {};
      const detectToken = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getToken() : null;
      if (detectToken) detectHeaders['Authorization'] = `Bearer ${detectToken}`;

      const res = await fetch(`${apiBase}/api/v1/reports/detect`, {
        method: 'POST',
        headers: detectHeaders,
        body: formData,
      });

      // Avoid race conditions if user changed image or invalidated while request was in flight
      if (requestId !== activeInferenceRequestId) return;

      if (mlScanningState) mlScanningState.style.display = 'none';

      if (!res.ok) {
        let errText = 'Inference could not be completed';
        try {
          const errData = await res.json();
          errText = errData.detail || errText;
        } catch (_) {}

        if (typeof CivicSightMLViewer !== 'undefined' && mlDetectionResultsSlot) {
          CivicSightMLViewer.render(mlDetectionResultsSlot, {
            imageUrl: dataUri,
            mlStatus: 'ML_FAILED',
            errorMessage: errText,
          });
        }
        return;
      }

      const detectionResult = await res.json();
      const rawDetections = detectionResult.detections || [];
      const numDetections = detectionResult.num_detections !== undefined ? detectionResult.num_detections : rawDetections.length;
      const mlStatus = (numDetections > 0) ? 'ML_COMPLETE' : 'ML_NO_DETECTIONS';

      const formattedDetections = rawDetections.map(d => ({
        type: d.class_name || d.detected_class,
        label: d.description || d.label || d.class_name,
        confidence: d.confidence,
        bbox: d.bbox_normalized || d.bbox,
        bboxFormat: 'xyxy',
        severity: d.severity,
      }));

      if (typeof CivicSightMLViewer !== 'undefined' && mlDetectionResultsSlot) {
        CivicSightMLViewer.render(mlDetectionResultsSlot, {
          imageUrl: dataUri,
          mlStatus: mlStatus,
          detections: formattedDetections,
          modelVersion: detectionResult.model_version || 'YOLOv8n-CivicSight-4Class',
          inferenceTimeMs: detectionResult.inference_time_ms,
        });
      }

    } catch (err) {
      if (requestId !== activeInferenceRequestId) return;
      if (mlScanningState) mlScanningState.style.display = 'none';
      if (typeof CivicSightMLViewer !== 'undefined' && mlDetectionResultsSlot) {
        CivicSightMLViewer.render(mlDetectionResultsSlot, {
          imageUrl: dataUri,
          mlStatus: 'ML_FAILED',
          errorMessage: 'Backend detection service is currently unreachable (Ensure FastAPI server is running on port 8000).',
        });
      }
    }
  }

  function handleConfirmDescription() {
    let hasError = false;

    // Check Step 1: Image
    if (!selectedImageFile || !selectedImageDataUri) {
      showToast('Please upload a damage photo in Step 1 first.', 'error');
      if (imageInputError) imageInputError.textContent = 'Please select a damage photo.';
      uploadDropzone?.focus();
      hasError = true;
    } else {
      if (imageInputError) imageInputError.textContent = '';
    }

    // Check Step 2: Description
    const desc = (damageDescription?.value || '').trim();
    if (!desc) {
      showToast('Please provide a problem description in Step 2.', 'error');
      if (descriptionError) descriptionError.textContent = 'Description is required and cannot be empty.';
      damageDescription?.focus();
      hasError = true;
    } else {
      if (descriptionError) descriptionError.textContent = '';
    }

    if (hasError) return;

    isAnalysisConfirmed = true;
    if (aiDamageResultsSection) {
      aiDamageResultsSection.style.display = 'block';
      aiDamageResultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    triggerImageInference(selectedImageFile, selectedImageDataUri);
  }

  const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/jpg', 'image/png', 'image/webp']);
  const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.jfif'];

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function handleFileSelect(file) {
    if (!file) return;

    const lowerName = (file.name || '').toLowerCase();
    const hasAllowedExt = ALLOWED_EXTENSIONS.some(ext => lowerName.endsWith(ext));
    const hasAllowedMime = file.type && ALLOWED_MIME_TYPES.has(file.type.toLowerCase());

    if (!hasAllowedMime || !hasAllowedExt) {
      damageImageInput.value = '';
      selectedImageFile = null;
      selectedImageDataUri = null;
      showToast('Unsupported file format. Please select a JPEG, PNG, or WEBP image.', 'error');
      if (imageInputError) imageInputError.textContent = 'Unsupported file format. Only JPEG, PNG, and WEBP images are allowed.';
      uploadDropzone?.classList.add('input-invalid');
      return;
    }

    if (file.size === 0) {
      damageImageInput.value = '';
      selectedImageFile = null;
      selectedImageDataUri = null;
      showToast('Selected file is empty (0 bytes). Please choose a valid photo.', 'error');
      if (imageInputError) imageInputError.textContent = 'Selected file is empty (0 bytes).';
      uploadDropzone?.classList.add('input-invalid');
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      damageImageInput.value = '';
      selectedImageFile = null;
      selectedImageDataUri = null;
      showToast('Image file exceeds the 15MB limit.', 'error');
      if (imageInputError) imageInputError.textContent = 'File exceeds 15MB limit.';
      uploadDropzone?.classList.add('input-invalid');
      return;
    }

    if (imageInputError) imageInputError.textContent = '';
    uploadDropzone?.classList.remove('input-invalid');

    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    previewFilename.textContent = file.name;
    previewFilesize.textContent = `${sizeInMB} MB`;

    // Invalidate prior analysis when image is changed or replaced
    invalidateAnalysis();

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUri = e.target.result;
      selectedImageFile = file;
      selectedImageDataUri = dataUri;
      imagePreview.src = dataUri;
      dropzoneIdle.style.display = 'none';
      previewContainer.style.display = 'flex';

      // Step 1: Do NOT run inference yet, do NOT display AI results card yet
    };
    reader.readAsDataURL(file);
  }

  function clearImageSelection() {
    selectedImageFile = null;
    selectedImageDataUri = null;
    damageImageInput.value = '';
    imagePreview.src = '';
    dropzoneIdle.style.display = 'block';
    previewContainer.style.display = 'none';
    if (imageInputError) imageInputError.textContent = '';
    invalidateAnalysis();
  }

  // Confirm description button and keyboard listener
  confirmDescriptionBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    handleConfirmDescription();
  });

  damageDescription?.addEventListener('keydown', (e) => {
    // Ctrl+Enter or Cmd+Enter explicitly confirms description without interfering with multiline typing
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleConfirmDescription();
    }
  });

  damageDescription?.addEventListener('input', () => {
    if (descriptionError && damageDescription.value.trim()) {
      descriptionError.textContent = '';
    }
    // Invalidate stale AI results if description is modified after analysis was triggered
    if (isAnalysisConfirmed) {
      invalidateAnalysis();
    }
  });

  if (uploadDropzone && damageImageInput) {
    uploadDropzone.addEventListener('click', (e) => {
      if (e.target !== removeImageBtn && !removeImageBtn?.contains(e.target)) {
        damageImageInput.click();
      }
    });

    uploadDropzone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        damageImageInput.click();
      }
    });

    damageImageInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      handleFileSelect(file);
    });

    ['dragenter', 'dragover'].forEach(name => {
      uploadDropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadDropzone.classList.add('drag-active');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      uploadDropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadDropzone.classList.remove('drag-active');
      });
    });

    uploadDropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const file = dt.files[0];
      if (file) {
        damageImageInput.files = dt.files;
        handleFileSelect(file);
      }
    });

    if (removeImageBtn) {
      removeImageBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearImageSelection();
      });
    }
  }

  // Clear validation errors on typing
  damageDescription?.addEventListener('input', () => {
    if (descriptionError) descriptionError.textContent = '';
    damageDescription.classList.remove('input-invalid');
  });

  // --- 5. Submission Status Banner Management ---
  function showStatus(state, data = {}) {
    if (!submissionStatus) return;
    submissionStatus.style.display = 'flex';
    submissionStatus.className = `submission-status-banner status-${state}`;

    if (state === 'submitting') {
      submissionStatus.innerHTML = `
        <div class="status-header">
          <svg class="status-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="2" x2="12" y2="6"></line>
            <line x1="12" y1="18" x2="12" y2="22"></line>
            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
            <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
            <line x1="2" y1="12" x2="6" y2="12"></line>
            <line x1="18" y1="12" x2="22" y2="12"></line>
            <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
            <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
          </svg>
          <span>Submitting Road Damage Report...</span>
        </div>
        <p class="status-body">Uploading photo and recording hazard coordinates in the municipal database...</p>
      `;
    } else if (state === 'success') {
      const createdDate = data.created_at ? new Date(data.created_at).toLocaleString() : new Date().toLocaleString();
      const apiBase = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';
      const statusNorm = (data.status || 'submitted').toLowerCase();
      const statusDisplay = statusNorm.replace(/_/g, ' ').toUpperCase();
      const priorityDisplay = data.priority ? String(data.priority).toUpperCase() : 'MEDIUM';
      const priorityReasons = Array.isArray(data.priority_reasons) ? data.priority_reasons : [];
      const currentUser = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getUser() : null;
      const isOfficerOrAdmin = currentUser && (currentUser.role === 'Municipal Officer' || currentUser.role === 'Admin');

      const rejectionBanner = (statusNorm === 'rejected' && data.rejection_reason)
        ? `<div class="status-rejection-box" style="margin-top: 0.75rem; padding: 0.75rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--color-danger-border); background: var(--color-danger-bg); color: var(--text-primary);">
             <strong style="color: var(--color-danger);">Rejection Reason:</strong> ${escapeHtml(data.rejection_reason)}
           </div>`
        : '';

      const afterImages = Array.isArray(data.after_images) ? data.after_images : [];
      const beforeAfterHtml = afterImages.length > 0
        ? `<div id="citizenBeforeAfterSection" style="margin-top: 1.25rem; padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-color); background: var(--bg-secondary);">
             <strong style="display: block; margin-bottom: 0.5rem;">Before &amp; After Repair Verification Photos (Read-Only)</strong>
             <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem;">
               <div>
                 <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">BEFORE (Citizen Photo)</div>
                 <img src="${escapeHtml(data.image_url ? (data.image_url.startsWith('http') ? data.image_url : apiBase + data.image_url) : '')}" alt="Before repair photo" style="width: 100%; max-height: 180px; object-fit: cover; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
               </div>
               <div>
                 <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">AFTER (Repair Evidence)</div>
                 <img id="citizenAfterEvidenceImg" src="" alt="After repair evidence photo" style="width: 100%; max-height: 180px; object-fit: cover; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
               </div>
             </div>
           </div>`
        : '';

      // Report submission success Lottie checkmark + Report ID text
      submissionStatus.innerHTML = `
        <div class="lottie-status-layout">
          <div class="lottie-wrap lottie-submission-status">
            <lottie-player src="../assets/lottie/success.json" background="transparent" speed="1" autoplay aria-hidden="true" style="width: 64px; height: 64px;"></lottie-player>
          </div>
          <div class="lottie-status-content">
            <div class="status-header">
              <span style="font-size: 1.15rem; font-weight: 700;">Report #${escapeHtml(data.id)} &mdash; ${escapeHtml(statusDisplay)}</span>
            </div>
            <div>
              <span class="status-id-badge">REPORT #${escapeHtml(data.id)}</span>
            </div>
            <p class="status-body" style="margin-top: 0.5rem;">
              ${statusNorm === 'rejected'
                ? 'This report was reviewed and rejected by a municipal officer.'
                : statusNorm === 'closed'
                ? 'Repair work has been completed, verified, and officially closed.'
                : 'Your road hazard report has been recorded in the municipal dispatch queue and classified for triage.'}
            </p>
            ${rejectionBanner}
          </div>
        </div>

        <!-- Municipal Verification & Report Lifecycle Status (Strictly separated from AI Assessment) -->
        <div class="status-details-grid" style="margin-top: 1rem;">
          <div class="status-details-item">
            <strong>Municipal Verification Status</strong>
            <span class="status-badge status-${escapeHtml(statusNorm)}" style="margin-top: 0.25rem;">
              <span class="status-badge-dot"></span>
              ${escapeHtml(statusDisplay)}
            </span>
          </div>
          <div class="status-details-item">
            <strong>Priority</strong>
            <span>${escapeHtml(priorityDisplay)}${priorityReasons.length ? ' &mdash; ' + escapeHtml(priorityReasons[0]) : ''}</span>
          </div>
          <div class="status-details-item">
            <strong>Coordinates</strong>
            <span>${escapeHtml(data.latitude)}, ${escapeHtml(data.longitude)}</span>
          </div>
          <div class="status-details-item">
            <strong>Submitted At</strong>
            <span>${escapeHtml(createdDate)}</span>
          </div>
        </div>

        ${beforeAfterHtml}

        <!-- Automated AI Assessment Slot (Enrichment / Decision Support) -->
        <div id="submissionMLAssessmentSlot" style="margin-top: 1.25rem;">
          <!-- Rendered via CivicSightMLViewer -->
        </div>

        <div class="status-actions" style="margin-top: 1.25rem;">
          <a href="my-reports.html" class="btn btn-primary btn-sm">Track in My Reports &rarr;</a>
          <button type="button" class="btn btn-secondary btn-sm" id="newReportBtn">Submit Another Report</button>
          ${isOfficerOrAdmin ? '<a href="dashboard.html" class="btn btn-secondary btn-sm">View in Municipal Dashboard &rarr;</a>' : ''}
        </div>
      `;

      // Load authenticated AFTER evidence photo via Blob URL if available
      if (afterImages.length > 0 && typeof CivicSightAuth !== 'undefined' && CivicSightAuth.fetchAuthenticatedImageUrl) {
        const firstAfter = afterImages[0];
        const afterUrl = `${apiBase}/api/v1/reports/${data.id}/evidence/${firstAfter.id}/file`;
        CivicSightAuth.fetchAuthenticatedImageUrl(afterUrl).then((blobUrl) => {
          const imgEl = document.getElementById('citizenAfterEvidenceImg');
          if (imgEl && blobUrl) imgEl.src = blobUrl;
        });
      }

      document.getElementById('newReportBtn')?.addEventListener('click', () => {
        submissionStatus.style.display = 'none';
        clearForm();
        if (window.history && window.history.pushState) {
          window.history.pushState({}, '', window.location.pathname);
        }
      });

      // Poll and render ML Assessment in background
      pollAndRenderMLAssessment(data.id, data);
    } else if (state === 'error') {
      // Error-state Lottie animation
      submissionStatus.innerHTML = `
        <div class="lottie-status-layout">
          <div class="lottie-wrap lottie-submission-status">
            <lottie-player src="../assets/lottie/error.json" background="transparent" speed="1" autoplay aria-hidden="true" style="width: 60px; height: 60px;"></lottie-player>
          </div>
          <div class="lottie-status-content">
            <div class="status-header">
              <span style="font-size: 1.1rem; font-weight: 700; color: var(--color-danger);">Submission Failed</span>
            </div>
            <p class="status-body" style="margin-top: 0.35rem;">${escapeHtml(data.message || 'An unexpected error occurred while submitting your report.')}</p>
            <div class="status-actions" style="margin-top: 0.75rem;">
              <button type="button" class="btn btn-secondary btn-sm" id="dismissErrorBtn">Dismiss</button>
            </div>
          </div>
        </div>
      `;

      document.getElementById('dismissErrorBtn')?.addEventListener('click', () => {
        submissionStatus.style.display = 'none';
      });
    }

    submissionStatus.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function clearForm() {
    roadDamageForm.reset();
    clearImageSelection();
    userEditedAddressManually = false;
    if (mapInstance && typeof mapInstance.clearAccuracy === 'function') {
      mapInstance.clearAccuracy();
    }
    if (submissionStatus) submissionStatus.style.display = 'none';
    if (descriptionError) descriptionError.textContent = '';
    if (imageInputError) imageInputError.textContent = '';
    if (latitudeError) latitudeError.textContent = '';
    if (longitudeError) longitudeError.textContent = '';
    document.querySelectorAll('.input-invalid').forEach(el => el.classList.remove('input-invalid'));
    requestBrowserGeolocation(false);
  }

  // --- 6. Form Submission Workflow ---
  let isSubmittingReport = false;
  if (roadDamageForm) {
    roadDamageForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (isSubmittingReport) return;

      const imageFile = selectedImageFile || (damageImageInput.files ? damageImageInput.files[0] : null);
      const desc = damageDescription.value.trim();
      const latVal = parseFloat(latitudeInput.value);
      const lonVal = parseFloat(longitudeInput.value);
      const addressText = addressTextInput.value.trim();

      // 1. Client-side UX Validation
      let hasError = false;

      if (!imageFile) {
        if (imageInputError) imageInputError.textContent = 'Please select a photo of the road damage.';
        uploadDropzone.classList.add('input-invalid');
        hasError = true;
      } else {
        if (imageInputError) imageInputError.textContent = '';
        uploadDropzone.classList.remove('input-invalid');
      }

      if (!desc) {
        if (descriptionError) descriptionError.textContent = 'Description is required.';
        damageDescription.classList.add('input-invalid');
        hasError = true;
      } else if (desc.length > 2000) {
        if (descriptionError) descriptionError.textContent = 'Description cannot exceed 2000 characters.';
        damageDescription.classList.add('input-invalid');
        hasError = true;
      } else {
        if (descriptionError) descriptionError.textContent = '';
        damageDescription.classList.remove('input-invalid');
      }

      if (isNaN(latVal) || latVal < -90 || latVal > 90) {
        if (latitudeError) latitudeError.textContent = 'Valid latitude between -90 and 90 is required.';
        latitudeInput.classList.add('input-invalid');
        hasError = true;
      } else {
        if (latitudeError) latitudeError.textContent = '';
        latitudeInput.classList.remove('input-invalid');
      }

      if (isNaN(lonVal) || lonVal < -180 || lonVal > 180) {
        if (longitudeError) longitudeError.textContent = 'Valid longitude between -180 and 180 is required.';
        longitudeInput.classList.add('input-invalid');
        hasError = true;
      } else {
        if (longitudeError) longitudeError.textContent = '';
        longitudeInput.classList.remove('input-invalid');
      }

      if (hasError) {
        showStatus('error', { message: 'Please complete all required fields highlighted in the form.' });
        showToast('Please fix form validation errors.', 'error');
        return;
      }

      // 2. Set Submitting UI State (double-click protected)
      isSubmittingReport = true;
      submitReportBtn.disabled = true;
      submitReportBtn.classList.add('btn-loading');
      submitReportBtn.innerHTML = `<span>Submitting...</span>`;
      showStatus('submitting');

      // 3. Assemble Multipart Form Data
      const formData = new FormData();
      formData.append('image', imageFile);
      formData.append('description', desc);
      formData.append('latitude', latVal.toString());
      formData.append('longitude', lonVal.toString());
      if (addressText) formData.append('address_text', addressText);

      // Attach Bearer token for authenticated citizen binding
      const reqHeaders = {};
      const authToken = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getToken() : null;
      if (authToken) reqHeaders['Authorization'] = `Bearer ${authToken}`;

      // 4. Submit to Backend API
      const apiBase = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';
      const endpoint1 = `${apiBase}/api/v1/reports`;
      const endpoint2 = `${apiBase}/reports`;

      try {
        let response;
        try {
          response = await fetch(endpoint1, {
            method: 'POST',
            headers: reqHeaders,
            body: formData,
          });
          if (response.status === 404) {
            response = await fetch(endpoint2, {
              method: 'POST',
              headers: reqHeaders,
              body: formData,
            });
          }
        } catch (fetchErr) {
          throw new Error(`Cannot connect to CivicSight backend server at ${apiBase}. Please check your network connection and retry.`);
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          const errorMsg = data.detail
            ? (Array.isArray(data.detail) ? data.detail.map(d => d.msg || JSON.stringify(d)).join(', ') : data.detail)
            : 'Failed to create report. Server rejected submission.';
          throw new Error(errorMsg);
        }

        // 5. Success State Handling
        showStatus('success', data);
        showToast(`Report #${data.id} submitted successfully!`, 'success');
        clearImageSelection();
        damageDescription.value = '';
        addressTextInput.value = '';

      } catch (err) {
        showStatus('error', { message: err.message || 'Submission error.' });
        showToast(err.message || 'Submission failed.', 'error');
      } finally {
        isSubmittingReport = false;
        submitReportBtn.disabled = false;
        submitReportBtn.classList.remove('btn-loading');
        submitReportBtn.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          <span>Submit Road Report</span>
        `;
      }
    });
  }

  if (resetFormBtn) {
    resetFormBtn.addEventListener('click', () => {
      clearForm();
      showToast('Form cleared.', 'info');
    });
  }

  // --- 7. Automated ML Assessment Polling & Rendering ---
  let activeReportPollTimer = null;

  async function pollAndRenderMLAssessment(reportId, initialReportData) {
    if (activeReportPollTimer) clearTimeout(activeReportPollTimer);
    const slot = document.getElementById('submissionMLAssessmentSlot');
    if (!slot || typeof CivicSightMLViewer === 'undefined') return;

    const apiBase = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';
    let fullImageUrl = '../assets/test_damage.jpg';
    if (initialReportData && initialReportData.image_url) {
      fullImageUrl = initialReportData.image_url.startsWith('http')
        ? initialReportData.image_url
        : `${apiBase}${initialReportData.image_url}`;
    }

    // Render initial ML_PENDING state
    CivicSightMLViewer.render(slot, {
      imageUrl: fullImageUrl,
      mlStatus: initialReportData?.ml_status || 'ML_PENDING',
      reportId: reportId,
      latitude: initialReportData?.latitude,
      longitude: initialReportData?.longitude,
      address: initialReportData?.address_text,
    });

    let attempts = 0;
    const maxAttempts = 20;

    async function checkStatus() {
      attempts++;
      try {
        const pollHeaders = {};
        const pollToken = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getToken() : null;
        if (pollToken) pollHeaders['Authorization'] = `Bearer ${pollToken}`;
        const res = await fetch(`${apiBase}/api/v1/reports/${reportId}/ml-status`, { headers: pollHeaders });
        if (res.ok) {
          const statusData = await res.json();
          if (statusData.ml_status !== 'ML_PENDING' || attempts >= maxAttempts) {
            // ML is complete, failed, or timed out. Fetch full report with detection_results.
            const headers = {};
            const token = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getToken() : null;
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const detailRes = await fetch(`${apiBase}/api/v1/reports/${reportId}`, { headers });
            let reportData = initialReportData;
            if (detailRes.ok) {
              reportData = await detailRes.json();
            } else {
              // Fallback to statusData
              reportData = {
                ...initialReportData,
                ml_status: statusData.ml_status,
                ml_model_version: statusData.ml_model_version,
                ml_inference_time_ms: statusData.ml_inference_time_ms,
                ml_error_message: statusData.ml_error_message,
              };
            }

            if (reportData.image_url) {
              fullImageUrl = reportData.image_url.startsWith('http')
                ? reportData.image_url
                : `${apiBase}${reportData.image_url}`;
            }

            const detections = (reportData.detection_results || []).map(d => {
              let parsedBbox = d.bbox_normalized;
              if (typeof parsedBbox === 'string') {
                try { parsedBbox = JSON.parse(parsedBbox); } catch (_) {}
              }
              return {
                type: d.detected_class,
                label: d.class_name,
                confidence: d.confidence,
                bbox: parsedBbox || [d.bbox_ymin, d.bbox_xmin, d.bbox_ymax, d.bbox_xmax],
                severity: d.severity,
              };
            });

            CivicSightMLViewer.render(slot, {
              imageUrl: fullImageUrl,
              mlStatus: reportData.ml_status || (detections.length > 0 ? 'ML_COMPLETE' : 'ML_NO_DETECTIONS'),
              detections: detections,
              latitude: reportData.latitude,
              longitude: reportData.longitude,
              address: reportData.address_text,
              reportId: reportData.id,
              modelVersion: reportData.ml_model_version || 'YOLOv8s-clean_rdd2022_yolov8s',
              inferenceTimeMs: reportData.ml_inference_time_ms,
              errorMessage: reportData.ml_error_message,
            });
            return;
          }
        } else if (res.status === 401 || res.status === 403) {
          return;
        }
      } catch (err) {
        console.warn('Error polling ML status for report #' + reportId, err);
      }

      if (attempts < maxAttempts) {
        activeReportPollTimer = setTimeout(checkStatus, 800);
      }
    }

    activeReportPollTimer = setTimeout(checkStatus, 800);
  }

  // --- 8. Load Existing Report View (if ?id=... present in URL) ---
  async function checkUrlForExistingReport() {
    const urlParams = new URLSearchParams(window.location.search);
    const reportId = urlParams.get('id');
    if (!reportId) return;

    const apiBase = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';
    const headers = {};
    const token = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getToken() : null;
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      const res = await fetch(`${apiBase}/api/v1/reports/${reportId}`, { headers });
      if (res.ok) {
        const report = await res.json();
        showStatus('success', report);
      } else if (res.status === 401) {
        showStatus('error', { message: 'Please log in to view this report.' });
      } else if (res.status === 403) {
        showStatus('error', { message: 'Access denied: You are not authorized to view this report.' });
      } else if (res.status === 404) {
        showStatus('error', { message: `Report #${reportId} was not found.` });
      }
    } catch (e) {
      showStatus('error', { message: 'Unable to load report details. Please verify your connection.' });
    }
  }

  // Initialize interactive map on DOM ready
  initMap();
  checkUrlForExistingReport();
});
