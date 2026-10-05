/**
 * CivicSight — Municipal Operations Dashboard & Interactive Map
 *
 * Week 6 Enhanced Implementation:
 * - Strict Route Guard: Citizens receive Access Denied screen & redirection; Unauthenticated redirected to login.
 * - Live Backend API Integration: Fetches from GET /api/v1/reports with JWT Bearer auth.
 * - Live Query Filtering: Dynamic filtering via ?status=... and ?priority=...
 * - Interactive Leaflet Map: Geospatial pins color-coded by priority (Red=HIGH, Amber=MEDIUM, Green=LOW).
 * - Deep Inspection Modal: Reuses CivicSightMLViewer for bounding box and defect triage.
 * - Real Lifecycle Status Transitions:
 *     * PATCH /reports/{id}/verify (moves to verified)
 *     * PATCH /reports/{id}/reject (prompts for required reason)
 *     * PATCH /reports/{id}/duplicate (prompts for required original report ID)
 *     * PATCH /reports/{id}/assign (prompts for required maintenance staff/crew)
 * - Server-Validated State Machine Rules mirrored on frontend (illegal actions hidden/disabled).
 * - Real Status Transition Audit History loaded from GET /reports/{id}/history.
 * - Established Theme-Aware Color Tokens for status badges across both Light and Dark modes.
 */

document.addEventListener('DOMContentLoaded', () => {
  // --------------------------------------------------------------------------
  // 1. Authentication & Route Guarding
  // --------------------------------------------------------------------------
  const token = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getToken() : null;
  const currentUser = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getUser() : null;

  if (!token || !currentUser) {
    window.location.replace('login.html?redirect=dashboard.html');
    return;
  }

  // Citizen role restriction: block access
  if (currentUser.role === 'Citizen') {
    const mainEl = document.querySelector('.dashboard-main');
    if (mainEl) {
      mainEl.innerHTML = `
        <div class="container" style="padding: 5rem 1rem; text-align: center; max-width: 620px; margin: 0 auto;">
          <div style="width: 80px; height: 80px; margin: 0 auto 1.75rem; border-radius: 50%; background: var(--accent-subtle); display: flex; align-items: center; justify-content: center; border: 1px solid var(--border-color); box-shadow: var(--shadow-md);">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
          </div>
          <h1 class="dashboard-title" style="font-size: 2rem; margin-bottom: 0.75rem;">Access Restricted</h1>
          <p class="dashboard-subtitle" style="margin-bottom: 2rem; font-size: 1.05rem; line-height: 1.6;">
            The <strong>Municipal Operations Center</strong> is restricted to authenticated <strong>Municipal Officers</strong> and <strong>Administrators</strong>.
            Your account is currently registered with the role <strong style="color: var(--accent-color);">${currentUser.role}</strong>.
          </p>
          <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
            <a href="report.html" class="btn btn-primary" style="min-width: 180px;">
              Citizen Road Reporting
            </a>
            <button type="button" class="btn btn-secondary" id="switchAccountBtn" style="min-width: 160px;">
              Switch Account
            </button>
          </div>
        </div>
      `;

      document.getElementById('switchAccountBtn')?.addEventListener('click', () => {
        CivicSightAuth.clearSession();
        window.location.href = 'login.html?redirect=dashboard.html';
      });
    }
    return;
  }

  // --------------------------------------------------------------------------
  // 2. DOM Elements
  // --------------------------------------------------------------------------
  const dashboardMapEl = document.getElementById('dashboardMap');
  const queueTableBody = document.getElementById('queueTableBody');
  const toastContainer = document.getElementById('toastContainer');

  // Inspection Modal Elements
  const inspectionModal = document.getElementById('inspectionModal');
  const closeInspectionModalBtn = document.getElementById('closeInspectionModalBtn');
  const modalCloseActionBtn = document.getElementById('modalCloseActionBtn');
  const modalReportSubheader = document.getElementById('modalReportSubheader');
  const modalMLViewerSlot = document.getElementById('modalMLViewerSlot');
  const modalCurrentStatusBadge = document.getElementById('modalCurrentStatusBadge');
  const modalCurrentStatusText = document.getElementById('modalCurrentStatusText');
  const modalExtraMeta = document.getElementById('modalExtraMeta');
  const modalHistoryTimeline = document.getElementById('modalHistoryTimeline');
  const historyCountBadge = document.getElementById('historyCountBadge');

  // Modal Action Buttons
  const modalVerifyBtn = document.getElementById('modalVerifyBtn');
  const modalAssignBtn = document.getElementById('modalAssignBtn');
  const modalDuplicateBtn = document.getElementById('modalDuplicateBtn');
  const modalRejectBtn = document.getElementById('modalRejectBtn');

  // Sub-Modal: Reject
  const rejectModal = document.getElementById('rejectModal');
  const closeRejectModalBtn = document.getElementById('closeRejectModalBtn');
  const cancelRejectBtn = document.getElementById('cancelRejectBtn');
  const rejectForm = document.getElementById('rejectForm');
  const rejectReasonInput = document.getElementById('rejectReasonInput');
  const rejectNoteInput = document.getElementById('rejectNoteInput');

  // Sub-Modal: Duplicate
  const duplicateModal = document.getElementById('duplicateModal');
  const closeDuplicateModalBtn = document.getElementById('closeDuplicateModalBtn');
  const cancelDuplicateBtn = document.getElementById('cancelDuplicateBtn');
  const duplicateForm = document.getElementById('duplicateForm');
  const duplicateOriginalSelect = document.getElementById('duplicateOriginalSelect');
  const duplicateOriginalInput = document.getElementById('duplicateOriginalInput');
  const duplicateNoteInput = document.getElementById('duplicateNoteInput');

  // Sub-Modal: Assign
  const assignModal = document.getElementById('assignModal');
  const closeAssignModalBtn = document.getElementById('closeAssignModalBtn');
  const cancelAssignBtn = document.getElementById('cancelAssignBtn');
  const assignForm = document.getElementById('assignForm');
  const assignStaffSelect = document.getElementById('assignStaffSelect');
  const assignCustomWrap = document.getElementById('assignCustomWrap');
  const assignCustomInput = document.getElementById('assignCustomInput');
  const assignNoteInput = document.getElementById('assignNoteInput');

  // Sub-Modal: Repair
  const repairModal = document.getElementById('repairModal');
  const closeRepairModalBtn = document.getElementById('closeRepairModalBtn');
  const confirmRepairDismissBtn = document.getElementById('confirmRepairDismissBtn');
  const repairTargetText = document.getElementById('repairTargetText');

  // Filter Elements
  const statusFilter = document.getElementById('statusFilter');
  const priorityFilter = document.getElementById('priorityFilter');
  const resetFiltersBtn = document.getElementById('resetFiltersBtn');

  // Metrics Elements
  const metricActiveTotal = document.getElementById('metricActiveTotal');
  const metricHighSeverity = document.getElementById('metricHighSeverity');
  const metricMediumSeverity = document.getElementById('metricMediumSeverity');
  const metricRepaired = document.getElementById('metricRepaired');

  const API_BASE = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';

  let map = null;
  let markersLayer = null;
  let tileLayer = null;
  let activeReports = [];
  let currentlyInspectedReportId = null;

  // --------------------------------------------------------------------------
  // Utility & Formatting Helpers
  // --------------------------------------------------------------------------
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatStatusLabel(status) {
    if (!status) return 'Submitted';
    const s = status.toLowerCase();
    switch (s) {
      case 'submitted': return 'Submitted';
      case 'pending_verification': return 'Pending Verification';
      case 'verified': return 'Verified';
      case 'assigned': return 'Assigned';
      case 'under_repair': return 'Under Repair';
      case 'repaired': return 'Repaired';
      case 'closed': return 'Closed';
      case 'rejected': return 'Rejected';
      case 'duplicate': return 'Duplicate';
      default: return status.replace(/_/g, ' ');
    }
  }

  function renderStatusBadge(status) {
    const s = (status || 'submitted').toLowerCase();
    const label = formatStatusLabel(s);
    return `<span class="status-badge status-${s}"><span class="status-badge-dot"></span>${label}</span>`;
  }

  // --------------------------------------------------------------------------
  // Tile Provider & Handling
  // --------------------------------------------------------------------------
  function cartoTileUrl() {
    const mode = (document.documentElement.getAttribute('data-theme') === 'dark') ? 'dark_all' : 'light_all';
    return `https://{s}.basemaps.cartocdn.com/${mode}/{z}/{x}/{y}{r}.png`;
  }
  const CARTO_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>';

  function attachTileErrorHandling(mapElement) {
    if (!tileLayer || !mapElement) return;
    let tileErrorCount = 0;
    tileLayer.on('tileload', () => { tileErrorCount = 0; hideMapError(mapElement); });
    tileLayer.on('tileerror', () => {
      tileErrorCount += 1;
      if (tileErrorCount >= 3) showMapError(mapElement);
    });
  }

  function showMapError(mapElement) {
    if (mapElement.querySelector('.map-error-overlay')) return;
    const overlay = document.createElement('div');
    overlay.className = 'map-error-overlay';
    overlay.innerHTML = `
      <div class="map-error-card">
        <strong>Map tiles could not be loaded</strong>
        <p>Check your internet connection, then retry. Report data remains available in the table below.</p>
        <button type="button" class="btn btn-secondary btn-sm" data-map-retry>Retry</button>
      </div>`;
    overlay.querySelector('[data-map-retry]').addEventListener('click', () => {
      overlay.remove();
      if (map) map.invalidateSize();
    });
    mapElement.appendChild(overlay);
  }

  function hideMapError(mapElement) {
    const overlay = mapElement.querySelector('.map-error-overlay');
    if (overlay) overlay.remove();
  }

  // --------------------------------------------------------------------------
  // Severity Pin Generator
  // --------------------------------------------------------------------------
  function createSeverityIcon(priority) {
    let pinColor = '#d97706'; // Medium Amber
    const norm = (priority || '').toUpperCase();
    if (norm === 'HIGH') pinColor = '#dc2626'; // High Red
    else if (norm === 'LOW') pinColor = '#16a34a'; // Low Green

    const svgHtml = `
      <svg class="severity-pin-svg" width="34" height="42" viewBox="0 0 34 42" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M17 41C17 41 31 25.5 31 16C31 7.71573 24.732 1 17 1C9.26801 1 3 7.71573 3 16C3 25.5 17 41 17 41Z" fill="${pinColor}" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round"/>
        <circle cx="17" cy="15" r="5.5" fill="#ffffff"/>
      </svg>
    `;

    return L.divIcon({
      className: 'severity-pin-icon',
      html: svgHtml,
      iconSize: [34, 42],
      iconAnchor: [17, 41],
      popupAnchor: [0, -38],
    });
  }

  // --------------------------------------------------------------------------
  // Map Initialization
  // --------------------------------------------------------------------------
  function initDashboardMap() {
    if (!dashboardMapEl || typeof L === 'undefined') return;

    map = L.map('dashboardMap', {
      zoomControl: true,
      attributionControl: true,
    }).setView([37.7760, -122.4180], 13);

    tileLayer = L.tileLayer(cartoTileUrl(), {
      maxZoom: 20,
      attribution: CARTO_ATTRIBUTION,
    }).addTo(map);

    attachTileErrorHandling(dashboardMapEl);

    const themeObserver = new MutationObserver(() => {
      if (tileLayer) map.removeLayer(tileLayer);
      tileLayer = L.tileLayer(cartoTileUrl(), { maxZoom: 20, attribution: CARTO_ATTRIBUTION }).addTo(map);
      attachTileErrorHandling(dashboardMapEl);
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    markersLayer = L.layerGroup().addTo(map);
  }

  // --------------------------------------------------------------------------
  // Render Map Markers
  // --------------------------------------------------------------------------
  function renderMarkers() {
    if (!markersLayer || !map) return;
    markersLayer.clearLayers();

    const validCoordinates = [];

    activeReports.forEach((report) => {
      if (typeof report.latitude !== 'number' || typeof report.longitude !== 'number') return;

      const priority = report.priority || 'MEDIUM';
      const marker = L.marker([report.latitude, report.longitude], {
        icon: createSeverityIcon(priority),
        title: `Report #${report.id} - ${priority} Priority`,
      });

      validCoordinates.push([report.latitude, report.longitude]);

      const damageCode = report.damage_type || 'D40';

      const popupContent = `
        <div class="dashboard-popup">
          <div class="popup-header">
            <span class="popup-report-id">Report #${report.id}</span>
            <span class="ml-severity-badge severity-${priority.toLowerCase()}">
              <span class="severity-bullet"></span>
              ${priority}
            </span>
          </div>

          <div class="popup-meta-row">
            <span class="popup-meta-label">Defect Type:</span>
            <span class="popup-meta-val">${damageCode} Pothole/Crack</span>
          </div>
          <div class="popup-meta-row">
            <span class="popup-meta-label">Address / Spot:</span>
            <span class="popup-meta-val">${escapeHtml(report.address_text) || 'Pinned Location'}</span>
          </div>
          <div class="popup-meta-row">
            <span class="popup-meta-label">Status:</span>
            <span class="popup-meta-val">${renderStatusBadge(report.status)}</span>
          </div>

          <div class="popup-actions" style="margin-top: 0.75rem;">
            <button type="button" class="btn btn-secondary btn-sm inspect-btn" data-report-id="${report.id}" style="width: 100%;">
              Open Deep Inspection
            </button>
          </div>
        </div>
      `;

      marker.bindPopup(popupContent, { maxWidth: 290 });
      markersLayer.addLayer(marker);
    });

    if (validCoordinates.length > 0 && map) {
      try {
        const bounds = L.latLngBounds(validCoordinates);
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
      } catch (e) {
        // Fallback
      }
    }

    map.off('popupopen');
    map.on('popupopen', () => {
      document.querySelectorAll('.inspect-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const reportId = parseInt(e.currentTarget.getAttribute('data-report-id'));
          openInspectionModal(reportId);
        });
      });
    });
  }

  // --------------------------------------------------------------------------
  // Triage Table Population
  // --------------------------------------------------------------------------
  function renderTriageTable() {
    if (!queueTableBody) return;
    queueTableBody.innerHTML = '';

    if (activeReports.length === 0) {
      const emptyTr = document.createElement('tr');
      emptyTr.innerHTML = `
        <td colspan="6" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          No municipal road hazard reports found matching current filter criteria.
        </td>
      `;
      queueTableBody.appendChild(emptyTr);
      updateMetrics();
      return;
    }

    activeReports.forEach((report) => {
      const priority = report.priority || 'MEDIUM';
      const damageCode = report.damage_type || 'D40';
      const status = (report.status || 'submitted').toLowerCase();

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>#${report.id}</strong></td>
        <td>
          <span class="detection-code-chip">${damageCode}</span>
        </td>
        <td>
          <div style="font-size: 0.85rem; font-weight: 500;">${escapeHtml(report.address_text) || 'Pinned Coordinates'}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${(report.latitude || 0).toFixed(4)}, ${(report.longitude || 0).toFixed(4)}</div>
        </td>
        <td>
          <span class="ml-severity-badge severity-${priority.toLowerCase()}">
            <span class="severity-bullet"></span>
            ${priority}
          </span>
        </td>
        <td>
          ${renderStatusBadge(status)}
        </td>
        <td>
          <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="CivicSightDashboard.openInspection(${report.id})">
              Inspect AI
            </button>
            ${(status === 'submitted' || status === 'pending_verification') ? `
              <button type="button" class="btn btn-primary btn-sm" onclick="CivicSightDashboard.verifyReport(${report.id})" id="tableVerifyBtn_${report.id}">
                Verify
              </button>
            ` : status === 'verified' ? `
              <button type="button" class="btn btn-primary btn-sm" onclick="CivicSightDashboard.openAssignModal(${report.id})" id="tableAssignBtn_${report.id}">
                Assign Crew
              </button>
            ` : status === 'assigned' ? `
              <button type="button" class="btn btn-secondary btn-sm" onclick="CivicSightDashboard.transitionStatus(${report.id}, 'under_repair')">
                Start Repair
              </button>
            ` : status === 'under_repair' ? `
              <button type="button" class="btn btn-secondary btn-sm" onclick="CivicSightDashboard.transitionStatus(${report.id}, 'repaired')">
                Mark Repaired
              </button>
            ` : `
              <span class="legend-dot green" title="Finished / Terminal State" style="margin: 0 0.5rem;"></span>
            `}
          </div>
        </td>
      `;
      queueTableBody.appendChild(tr);
    });

    updateMetrics();
  }

  // --------------------------------------------------------------------------
  // Update KPI Metrics Counters
  // --------------------------------------------------------------------------
  function updateMetrics() {
    const total = activeReports.length;
    const high = activeReports.filter(r => (r.priority || '').toUpperCase() === 'HIGH').length;
    const medium = activeReports.filter(r => (r.priority || '').toUpperCase() === 'MEDIUM').length;
    const repaired = activeReports.filter(r => r.status === 'repaired' || r.status === 'closed').length;

    if (metricActiveTotal) metricActiveTotal.textContent = Math.max(0, total - repaired);
    if (metricHighSeverity) metricHighSeverity.textContent = high;
    if (metricMediumSeverity) metricMediumSeverity.textContent = medium;
    if (metricRepaired) metricRepaired.textContent = repaired;
  }

  // --------------------------------------------------------------------------
  // Fetch Reports from Backend
  // --------------------------------------------------------------------------
  async function fetchReports() {
    try {
      const params = new URLSearchParams();
      const statusVal = statusFilter ? statusFilter.value.trim() : '';
      const priorityVal = priorityFilter ? priorityFilter.value.trim() : '';

      if (statusVal) params.append('status', statusVal);
      if (priorityVal) params.append('priority', priorityVal);

      let url = `${API_BASE}/api/v1/reports`;
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const res = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/json',
        }
      });

      if (res.status === 401) {
        showToast('Session expired. Please log in again.', 'error');
        CivicSightAuth.clearSession();
        window.location.href = 'login.html?redirect=dashboard.html';
        return;
      }

      if (res.status === 403) {
        showToast('Access forbidden: Municipal Officer or Admin credentials required.', 'error');
        return;
      }

      if (!res.ok) {
        throw new Error(`Failed to load reports (${res.status})`);
      }

      const data = await res.json();
      activeReports = Array.isArray(data) ? data : [];

      renderMarkers();
      renderTriageTable();
    } catch (err) {
      console.error('Error fetching reports from backend:', err);
      showToast('Error syncing with backend reports API.', 'error');
    }
  }

  // --------------------------------------------------------------------------
  // Inspection Modal & Detail View
  // --------------------------------------------------------------------------
  async function openInspectionModal(reportId) {
    currentlyInspectedReportId = reportId;
    let report = activeReports.find(r => r.id === reportId);

    // Fetch full details from GET /reports/{id}
    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/json',
        }
      });
      if (res.ok) {
        report = await res.json();
        const idx = activeReports.findIndex(r => r.id === reportId);
        if (idx !== -1) activeReports[idx] = report;
      }
    } catch (e) {
      console.warn('Could not fetch single report detail, using active cache:', e);
    }

    if (!report) return;

    if (modalReportSubheader) {
      const createdDate = report.created_at ? new Date(report.created_at).toLocaleString() : 'Recent';
      modalReportSubheader.textContent = `Report #${report.id} • Registered on ${createdDate} • ${report.address_text || 'Pinned Location'}`;
    }

    // Resolve Image URL
    let fullImageUrl = '../assets/test_damage.jpg';
    if (report.image_url) {
      fullImageUrl = report.image_url.startsWith('http') ? report.image_url : `${API_BASE}${report.image_url}`;
    }

    // Resolve Detections
    let detections = report.ml_detections;
    if (!detections || (Array.isArray(detections) && detections.length === 0)) {
      if (typeof CivicSightMLViewer !== 'undefined') {
        detections = CivicSightMLViewer.generateSyntheticDetections(report.damage_type || 'D40');
      }
    }

    // Render using reusable CivicSightMLViewer
    if (modalMLViewerSlot && typeof CivicSightMLViewer !== 'undefined') {
      CivicSightMLViewer.render(modalMLViewerSlot, {
        imageUrl: fullImageUrl,
        detections: detections,
        latitude: report.latitude,
        longitude: report.longitude,
        address: report.address_text,
        reportId: report.id,
      });
    }

    // Update Modal Verification & Action Buttons state
    updateModalVerificationState(report);

    // Load REAL Status Transition History from Backend
    await loadReportHistory(reportId);

    if (inspectionModal) inspectionModal.classList.add('open');
  }

  // --------------------------------------------------------------------------
  // Update Modal State & Button Controls (Mirroring Backend Transition Rules)
  // --------------------------------------------------------------------------
  function updateModalVerificationState(report) {
    if (!modalCurrentStatusBadge) return;

    const status = (report.status || 'submitted').toLowerCase();

    // 1. Update Status Badge with established color tokens
    modalCurrentStatusBadge.className = `status-badge status-${status}`;
    if (modalCurrentStatusText) {
      modalCurrentStatusText.textContent = formatStatusLabel(status);
    }

    // 2. Extra Metadata Summary (Assigned crew, Rejection reason, Duplicate ref)
    if (modalExtraMeta) {
      const metaParts = [];
      if (report.assigned_to) {
        metaParts.push(`<strong>Assigned Crew:</strong> ${escapeHtml(report.assigned_to)}`);
      }
      if (report.duplicate_of_id) {
        metaParts.push(`<strong>Duplicate of:</strong> Work Order #${report.duplicate_of_id}`);
      }
      if (report.rejection_reason) {
        metaParts.push(`<strong style="color: var(--color-danger);">Rejection Reason:</strong> ${escapeHtml(report.rejection_reason)}`);
      }
      modalExtraMeta.innerHTML = metaParts.length > 0 ? metaParts.join(' &bull; ') : '';
    }

    // 3. Mirror Legal Transition Map strictly
    // Submitted & Pending Verification: can Verify, Reject, or Duplicate. CANNOT Assign yet.
    const isSubOrPending = (status === 'submitted' || status === 'pending_verification');
    const isVerified = (status === 'verified');
    const isAssigned = (status === 'assigned');
    const isUnderRepair = (status === 'under_repair');
    const isTerminal = ['repaired', 'closed', 'rejected', 'duplicate'].includes(status);

    if (modalVerifyBtn) {
      if (isSubOrPending) {
        modalVerifyBtn.style.display = 'inline-flex';
        modalVerifyBtn.disabled = false;
        modalVerifyBtn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
          Verify Report
        `;
      } else {
        modalVerifyBtn.style.display = 'none';
      }
    }

    if (modalRejectBtn) {
      if (isSubOrPending) {
        modalRejectBtn.style.display = 'inline-flex';
        modalRejectBtn.disabled = false;
      } else {
        modalRejectBtn.style.display = 'none';
      }
    }

    if (modalDuplicateBtn) {
      if (isSubOrPending) {
        modalDuplicateBtn.style.display = 'inline-flex';
        modalDuplicateBtn.disabled = false;
      } else {
        modalDuplicateBtn.style.display = 'none';
      }
    }

    if (modalAssignBtn) {
      if (isVerified) {
        modalAssignBtn.style.display = 'inline-flex';
        modalAssignBtn.disabled = false;
      } else {
        modalAssignBtn.style.display = 'none';
      }
    }
  }

  // --------------------------------------------------------------------------
  // Real Status Transition History Audit Timeline (GET /reports/{id}/history)
  // --------------------------------------------------------------------------
  async function loadReportHistory(reportId) {
    if (!modalHistoryTimeline) return;

    modalHistoryTimeline.innerHTML = `
      <div style="padding: 1.25rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
        Loading transition history...
      </div>
    `;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/history`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/json',
        }
      });

      if (!res.ok) {
        throw new Error(`History fetch failed with status ${res.status}`);
      }

      const historyData = await res.json();
      const records = Array.isArray(historyData) ? historyData : [];

      if (historyCountBadge) {
        historyCountBadge.textContent = `${records.length} ${records.length === 1 ? 'event' : 'events'}`;
      }

      if (records.length === 0) {
        modalHistoryTimeline.innerHTML = `
          <div class="history-empty-msg">No status history recorded yet for this report.</div>
        `;
        return;
      }

      // Sort chronological ascending (or already returned sorted)
      modalHistoryTimeline.innerHTML = records.map((entry) => {
        const timeFormatted = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Recorded';
        const fromStatus = entry.from_status ? formatStatusLabel(entry.from_status) : null;
        const toStatus = formatStatusLabel(entry.to_status);
        const performerName = entry.changed_by_name || 'System / Officer';
        const performerRole = entry.role ? ` (${entry.role})` : '';

        const transitionLabel = fromStatus
          ? `${renderStatusBadge(entry.from_status)} <span style="color: var(--text-muted);">&rarr;</span> ${renderStatusBadge(entry.to_status)}`
          : `${renderStatusBadge(entry.to_status)} <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.25rem;">(Initial Submission)</span>`;

        return `
          <div class="history-timeline-item">
            <div class="history-timeline-node"></div>
            <div class="history-timeline-content">
              <div class="history-header-row">
                <div class="history-transition-badge">
                  ${transitionLabel}
                </div>
                <div class="history-time">${timeFormatted}</div>
              </div>
              <div class="history-performer">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                <span>Recorded by <strong>${escapeHtml(performerName)}</strong>${performerRole}</span>
              </div>
              ${entry.note ? `
                <div class="history-note-box">
                  <strong>Note / Reason:</strong> ${escapeHtml(entry.note)}
                </div>
              ` : ''}
            </div>
          </div>
        `;
      }).join('');

    } catch (err) {
      console.error('Error fetching report history:', err);
      modalHistoryTimeline.innerHTML = `
        <div style="padding: 1rem; color: var(--color-danger); font-size: 0.85rem; text-align: center;">
          Failed to load status history timeline from backend.
        </div>
      `;
    }
  }

  // --------------------------------------------------------------------------
  // Close Modals
  // --------------------------------------------------------------------------
  function closeInspectionModal() {
    if (inspectionModal) inspectionModal.classList.remove('open');
    currentlyInspectedReportId = null;
  }

  closeInspectionModalBtn?.addEventListener('click', closeInspectionModal);
  modalCloseActionBtn?.addEventListener('click', closeInspectionModal);
  inspectionModal?.addEventListener('click', (e) => {
    if (e.target === inspectionModal) closeInspectionModal();
  });

  // --------------------------------------------------------------------------
  // Lifecycle Action 1: PATCH /reports/{id}/verify
  // --------------------------------------------------------------------------
  async function verifyReport(reportId) {
    if (!reportId) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/verify`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ note: 'Verified by Municipal Officer from operations center.' })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        showToast(errorData.detail || `Verification failed (${res.status})`, 'error');
        return;
      }

      const updatedReport = await res.json();

      // Immediate in-memory state update
      const target = activeReports.find(r => r.id === reportId);
      if (target) {
        target.status = updatedReport.status || 'verified';
        if (updatedReport.priority) target.priority = updatedReport.priority;
      }

      renderMarkers();
      renderTriageTable();
      updateMetrics();

      if (currentlyInspectedReportId === reportId) {
        updateModalVerificationState(updatedReport);
        await loadReportHistory(reportId);
      }

      showToast(`Report #${reportId} verified successfully.`, 'success');
    } catch (err) {
      console.error('Error verifying report:', err);
      showToast('Network error while verifying report.', 'error');
    }
  }

  modalVerifyBtn?.addEventListener('click', () => {
    if (currentlyInspectedReportId) {
      verifyReport(currentlyInspectedReportId);
    }
  });

  // --------------------------------------------------------------------------
  // Lifecycle Action 2: PATCH /reports/{id}/reject
  // --------------------------------------------------------------------------
  function openRejectModal(reportId) {
    if (rejectReasonInput) rejectReasonInput.value = '';
    if (rejectNoteInput) rejectNoteInput.value = '';
    if (rejectModal) rejectModal.classList.add('open');
  }

  function closeRejectModal() {
    if (rejectModal) rejectModal.classList.remove('open');
  }

  closeRejectModalBtn?.addEventListener('click', closeRejectModal);
  cancelRejectBtn?.addEventListener('click', closeRejectModal);
  rejectModal?.addEventListener('click', (e) => {
    if (e.target === rejectModal) closeRejectModal();
  });

  modalRejectBtn?.addEventListener('click', () => {
    if (currentlyInspectedReportId) {
      openRejectModal(currentlyInspectedReportId);
    }
  });

  rejectForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const reportId = currentlyInspectedReportId;
    if (!reportId) return;

    const reason = rejectReasonInput ? rejectReasonInput.value.trim() : '';
    const note = rejectNoteInput ? rejectNoteInput.value.trim() : '';

    if (!reason) {
      showToast('A specific rejection reason is required.', 'error');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/reject`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ reason: reason, note: note || null })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        showToast(errorData.detail || `Rejection failed (${res.status})`, 'error');
        return;
      }

      const updatedReport = await res.json();
      const target = activeReports.find(r => r.id === reportId);
      if (target) {
        target.status = updatedReport.status || 'rejected';
        target.rejection_reason = reason;
      }

      closeRejectModal();
      renderMarkers();
      renderTriageTable();
      updateMetrics();

      if (currentlyInspectedReportId === reportId) {
        updateModalVerificationState(updatedReport);
        await loadReportHistory(reportId);
      }

      showToast(`Report #${reportId} has been marked as Rejected.`, 'info');
    } catch (err) {
      console.error('Error rejecting report:', err);
      showToast('Network error while rejecting report.', 'error');
    }
  });

  // --------------------------------------------------------------------------
  // Lifecycle Action 3: PATCH /reports/{id}/duplicate
  // --------------------------------------------------------------------------
  function openDuplicateModal(reportId) {
    if (duplicateOriginalInput) duplicateOriginalInput.value = '';
    if (duplicateNoteInput) duplicateNoteInput.value = '';

    // Populate selection options from active reports (excluding self)
    if (duplicateOriginalSelect) {
      duplicateOriginalSelect.innerHTML = `<option value="">-- Select from Active Reports --</option>`;
      activeReports.forEach((r) => {
        if (r.id !== reportId) {
          const opt = document.createElement('option');
          opt.value = r.id;
          opt.textContent = `Report #${r.id} (${r.damage_type || 'Defect'} - ${r.address_text || 'Pinned Location'})`;
          duplicateOriginalSelect.appendChild(opt);
        }
      });
    }

    if (duplicateModal) duplicateModal.classList.add('open');
  }

  duplicateOriginalSelect?.addEventListener('change', (e) => {
    if (e.target.value && duplicateOriginalInput) {
      duplicateOriginalInput.value = e.target.value;
    }
  });

  function closeDuplicateModal() {
    if (duplicateModal) duplicateModal.classList.remove('open');
  }

  closeDuplicateModalBtn?.addEventListener('click', closeDuplicateModal);
  cancelDuplicateBtn?.addEventListener('click', closeDuplicateModal);
  duplicateModal?.addEventListener('click', (e) => {
    if (e.target === duplicateModal) closeDuplicateModal();
  });

  modalDuplicateBtn?.addEventListener('click', () => {
    if (currentlyInspectedReportId) {
      openDuplicateModal(currentlyInspectedReportId);
    }
  });

  duplicateForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const reportId = currentlyInspectedReportId;
    if (!reportId) return;

    const originalIdVal = duplicateOriginalInput ? parseInt(duplicateOriginalInput.value) : null;
    const note = duplicateNoteInput ? duplicateNoteInput.value.trim() : '';

    if (!originalIdVal || isNaN(originalIdVal)) {
      showToast('A valid original report ID is required.', 'error');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/duplicate`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ original_report_id: originalIdVal, note: note || null })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        showToast(errorData.detail || `Duplicate operation failed (${res.status})`, 'error');
        return;
      }

      const updatedReport = await res.json();
      const target = activeReports.find(r => r.id === reportId);
      if (target) {
        target.status = updatedReport.status || 'duplicate';
        target.duplicate_of_id = originalIdVal;
      }

      closeDuplicateModal();
      renderMarkers();
      renderTriageTable();
      updateMetrics();

      if (currentlyInspectedReportId === reportId) {
        updateModalVerificationState(updatedReport);
        await loadReportHistory(reportId);
      }

      showToast(`Report #${reportId} marked as Duplicate of #${originalIdVal}.`, 'info');
    } catch (err) {
      console.error('Error marking duplicate:', err);
      showToast('Network error while marking duplicate.', 'error');
    }
  });

  // --------------------------------------------------------------------------
  // Lifecycle Action 4: PATCH /reports/{id}/assign
  // --------------------------------------------------------------------------
  function openAssignModal(reportId) {
    currentlyInspectedReportId = reportId;
    if (assignStaffSelect) assignStaffSelect.value = 'Metro Asphalt Crew Alpha';
    if (assignCustomWrap) assignCustomWrap.style.display = 'none';
    if (assignCustomInput) assignCustomInput.value = '';
    if (assignNoteInput) assignNoteInput.value = '';
    if (assignModal) assignModal.classList.add('open');
  }

  assignStaffSelect?.addEventListener('change', (e) => {
    if (assignCustomWrap) {
      assignCustomWrap.style.display = e.target.value === 'custom' ? 'block' : 'none';
    }
  });

  function closeAssignModal() {
    if (assignModal) assignModal.classList.remove('open');
  }

  closeAssignModalBtn?.addEventListener('click', closeAssignModal);
  cancelAssignBtn?.addEventListener('click', closeAssignModal);
  assignModal?.addEventListener('click', (e) => {
    if (e.target === assignModal) closeAssignModal();
  });

  modalAssignBtn?.addEventListener('click', () => {
    if (currentlyInspectedReportId) {
      openAssignModal(currentlyInspectedReportId);
    }
  });

  assignForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const reportId = currentlyInspectedReportId;
    if (!reportId) return;

    let assignee = assignStaffSelect ? assignStaffSelect.value : '';
    if (assignee === 'custom') {
      assignee = assignCustomInput ? assignCustomInput.value.trim() : '';
    }
    const note = assignNoteInput ? assignNoteInput.value.trim() : '';

    if (!assignee) {
      showToast('A maintenance crew or technician must be designated.', 'error');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/assign`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ assigned_to: assignee, note: note || null })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        showToast(errorData.detail || `Assignment failed (${res.status})`, 'error');
        return;
      }

      const updatedReport = await res.json();
      const target = activeReports.find(r => r.id === reportId);
      if (target) {
        target.status = updatedReport.status || 'assigned';
        target.assigned_to = assignee;
      }

      closeAssignModal();
      renderMarkers();
      renderTriageTable();
      updateMetrics();

      if (currentlyInspectedReportId === reportId) {
        updateModalVerificationState(updatedReport);
        await loadReportHistory(reportId);
      }

      showToast(`Work order #${reportId} dispatched to ${assignee}.`, 'success');
    } catch (err) {
      console.error('Error assigning report:', err);
      showToast('Network error while assigning crew.', 'error');
    }
  });

  // --------------------------------------------------------------------------
  // Generic Transition Helper (e.g. Under Repair -> Repaired)
  // --------------------------------------------------------------------------
  async function transitionStatus(reportId, newStatus) {
    if (!reportId) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/status`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          status: newStatus,
          note: `Transitioned to ${formatStatusLabel(newStatus)} via Operations Console.`
        })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        showToast(errorData.detail || `Status update failed (${res.status})`, 'error');
        return;
      }

      const updatedReport = await res.json();
      const target = activeReports.find(r => r.id === reportId);
      if (target) {
        target.status = updatedReport.status;
      }

      renderMarkers();
      renderTriageTable();
      updateMetrics();

      if (currentlyInspectedReportId === reportId) {
        updateModalVerificationState(updatedReport);
        await loadReportHistory(reportId);
      }

      if (newStatus === 'repaired' || newStatus === 'closed') {
        if (repairTargetText) repairTargetText.textContent = `Report #${reportId} Marked Repaired`;
        if (repairModal) repairModal.classList.add('open');
      }

      showToast(`Report #${reportId} transitioned to ${formatStatusLabel(newStatus)}.`, 'success');
    } catch (err) {
      console.error('Error transitioning report status:', err);
      showToast('Network error while transitioning status.', 'error');
    }
  }

  function closeRepairModal() {
    if (repairModal) repairModal.classList.remove('open');
  }

  closeRepairModalBtn?.addEventListener('click', closeRepairModal);
  confirmRepairDismissBtn?.addEventListener('click', closeRepairModal);
  repairModal?.addEventListener('click', (e) => {
    if (e.target === repairModal) closeRepairModal();
  });

  // --------------------------------------------------------------------------
  // Filter Event Listeners
  // --------------------------------------------------------------------------
  statusFilter?.addEventListener('change', () => fetchReports());
  priorityFilter?.addEventListener('change', () => fetchReports());
  resetFiltersBtn?.addEventListener('click', () => {
    if (statusFilter) statusFilter.value = '';
    if (priorityFilter) priorityFilter.value = '';
    fetchReports();
  });

  // --------------------------------------------------------------------------
  // Toast Notification Helper
  // --------------------------------------------------------------------------
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
      <span>${escapeHtml(message)}</span>
    `;

    toastContainer.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Global methods for table row actions
  window.CivicSightDashboard = {
    openInspection: openInspectionModal,
    verifyReport: verifyReport,
    openAssignModal: openAssignModal,
    transitionStatus: transitionStatus,
  };

  // Initialize
  initDashboardMap();
  fetchReports();
});
