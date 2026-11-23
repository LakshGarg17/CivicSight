/**
 * CivicSight — Citizen Portal: Track My Reports & Live Municipal Progress
 *
 * Provides real-time tracking for all citizen-submitted road hazards:
 * - Direct authenticated querying against GET /api/v1/reports/mine (strict anti-IDOR).
 * - Canonical user-friendly lifecycle status badges matching the authoritative backend state machine.
 * - Deep Inspection Modal reusing CivicSightMLViewer for bounding boxes and AI detections.
 * - Side-by-side Before/After repair evidence verification.
 * - Chronological municipal action timeline with officer and field crew remarks.
 * - Automatic background synchronization (polling every 12 seconds).
 */

(function () {
  'use strict';

  const API_BASE = window.location.origin.includes(':3000') || window.location.origin.includes(':8080')
    ? 'http://127.0.0.1:8000'
    : '';

  // Canonical User-Friendly Status Mappings
  const CANONICAL_STATUS_LABELS = {
    'submitted': 'Submitted — Awaiting Verification',
    'pending_verification': 'Under Verification',
    'verified': 'Verified',
    'assigned': 'Assigned to Maintenance Team',
    'under_repair': 'Work In Progress',
    'repair_evidence_submitted': 'Repair Completed — Awaiting Final Verification',
    'closed': 'Closed / Completed',
    'repaired': 'Closed / Completed',
    'rejected': 'Rejected',
    'duplicate': 'Duplicate Incident',
  };

  const DEFECT_LABELS = {
    'D00': 'Longitudinal Crack',
    'D10': 'Transverse Crack',
    'D20': 'Alligator Cracking',
    'D40': 'Pothole',
  };

  // State
  let myReports = [];
  let currentTab = 'all'; // 'all' | 'active' | 'closed' | 'rejected'
  let currentlyInspectedReportId = null;
  let pollingInterval = null;

  // DOM Elements
  const refreshBtn = document.getElementById('refreshBtn');
  const reportsLoading = document.getElementById('reportsLoading');
  const reportsEmpty = document.getElementById('reportsEmpty');
  const reportsGrid = document.getElementById('reportsGrid');

  const metricTotal = document.getElementById('metricTotal');
  const metricPending = document.getElementById('metricPending');
  const metricActive = document.getElementById('metricActive');
  const metricClosed = document.getElementById('metricClosed');

  const countAll = document.getElementById('countAll');
  const countActive = document.getElementById('countActive');
  const countClosed = document.getElementById('countClosed');
  const countRejected = document.getElementById('countRejected');

  // Inspection Modal DOM Elements
  const citizenDetailModal = document.getElementById('citizenDetailModal');
  const closeDetailModalBtn = document.getElementById('closeDetailModalBtn');
  const closeDetailModalFooterBtn = document.getElementById('closeDetailModalFooterBtn');
  const modalDetailTitle = document.getElementById('modalDetailTitle');
  const modalDetailSubheader = document.getElementById('modalDetailSubheader');
  const modalDetailStatusBadge = document.getElementById('modalDetailStatusBadge');
  const modalDetailStatusText = document.getElementById('modalDetailStatusText');
  const modalAlertBanner = document.getElementById('modalAlertBanner');
  const modalBeforeAfterWrap = document.getElementById('modalBeforeAfterWrap');
  const modalBeforeImg = document.getElementById('modalBeforeImg');
  const modalAfterImg = document.getElementById('modalAfterImg');
  const modalMLViewerSlot = document.getElementById('modalMLViewerSlot');
  const modalLocationText = document.getElementById('modalLocationText');
  const modalCoordsText = document.getElementById('modalCoordsText');
  const modalPriorityText = document.getElementById('modalPriorityText');
  const modalCrewText = document.getElementById('modalCrewText');
  const modalDescriptionText = document.getElementById('modalDescriptionText');
  const modalTimeline = document.getElementById('modalTimeline');

  // --------------------------------------------------------------------------
  // 1. Session & Role Verification
  // --------------------------------------------------------------------------
  function checkSession() {
    if (typeof CivicSightAuth === 'undefined' || !CivicSightAuth.isAuthenticated()) {
      window.location.replace('login.html?redirect=my-reports.html');
      return false;
    }
    const user = CivicSightAuth.getUser();
    if (!user) {
      window.location.replace('login.html?redirect=my-reports.html');
      return false;
    }
    return true;
  }

  function getAuthHeaders() {
    const token = CivicSightAuth.getToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    };
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatStatusLabel(status) {
    const norm = (status || '').toLowerCase().trim();
    return CANONICAL_STATUS_LABELS[norm] || norm.replace(/_/g, ' ').toUpperCase();
  }

  function resolveDefectLabel(damageType) {
    if (!damageType) return 'Unclassified Hazard';
    const code = damageType.trim().toUpperCase();
    return DEFECT_LABELS[code] || damageType;
  }

  function resolveImageUrl(rawUrl) {
    if (!rawUrl) return '../assets/logo-icon.png';
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) return rawUrl;
    return `${API_BASE}${rawUrl.startsWith('/') ? rawUrl : '/' + rawUrl}`;
  }

  // --------------------------------------------------------------------------
  // 2. Data Fetching & Sync
  // --------------------------------------------------------------------------
  async function fetchMyReports(silent = false) {
    if (!checkSession()) return;

    if (!silent && reportsLoading) reportsLoading.style.display = 'block';

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/mine`, {
        headers: getAuthHeaders(),
      });

      if (res.status === 401) {
        CivicSightAuth.logout();
        return;
      }

      if (!res.ok) {
        throw new Error(`Failed to load reports (${res.status})`);
      }

      myReports = await res.json();
      updateMetrics();
      renderReports();

      // If a report is currently open in modal, refresh its detail
      if (currentlyInspectedReportId && citizenDetailModal?.classList.contains('open')) {
        const currentOpen = myReports.find(r => r.id === currentlyInspectedReportId);
        if (currentOpen) {
          updateModalUI(currentOpen);
        }
      }
    } catch (err) {
      console.error('Error fetching citizen reports:', err);
      if (!silent) {
        CivicSightAuth.showToast('Unable to synchronize report statuses with municipal server.', 'error');
      }
    } finally {
      if (reportsLoading) reportsLoading.style.display = 'none';
    }
  }

  // --------------------------------------------------------------------------
  // 3. Metrics & Tab Calculation
  // --------------------------------------------------------------------------
  function updateMetrics() {
    const total = myReports.length;
    const pending = myReports.filter(r => ['submitted', 'pending_verification'].includes((r.status || '').toLowerCase())).length;
    const active = myReports.filter(r => ['verified', 'assigned', 'under_repair', 'repair_evidence_submitted'].includes((r.status || '').toLowerCase())).length;
    const closed = myReports.filter(r => ['closed', 'repaired'].includes((r.status || '').toLowerCase())).length;
    const rejected = myReports.filter(r => (r.status || '').toLowerCase() === 'rejected').length;

    if (metricTotal) metricTotal.textContent = total;
    if (metricPending) metricPending.textContent = pending;
    if (metricActive) metricActive.textContent = active;
    if (metricClosed) metricClosed.textContent = closed;

    if (countAll) countAll.textContent = total;
    if (countActive) countActive.textContent = active + pending;
    if (countClosed) countClosed.textContent = closed;
    if (countRejected) countRejected.textContent = rejected;
  }

  function getFilteredReports() {
    if (currentTab === 'active') {
      return myReports.filter(r => !['closed', 'repaired', 'rejected'].includes((r.status || '').toLowerCase()));
    } else if (currentTab === 'closed') {
      return myReports.filter(r => ['closed', 'repaired'].includes((r.status || '').toLowerCase()));
    } else if (currentTab === 'rejected') {
      return myReports.filter(r => (r.status || '').toLowerCase() === 'rejected');
    }
    return myReports;
  }

  // --------------------------------------------------------------------------
  // 4. Reports Grid & Card Rendering
  // --------------------------------------------------------------------------
  function renderReports() {
    const list = getFilteredReports();

    if (!list || list.length === 0) {
      if (reportsEmpty) reportsEmpty.style.display = 'block';
      if (reportsGrid) reportsGrid.style.display = 'none';
      return;
    }

    if (reportsEmpty) reportsEmpty.style.display = 'none';
    if (reportsGrid) {
      reportsGrid.style.display = 'grid';
      reportsGrid.innerHTML = list.map(r => renderReportCard(r)).join('');
    }
  }

  function renderReportCard(report) {
    const statusNorm = (report.status || 'submitted').toLowerCase();
    const statusLabel = formatStatusLabel(statusNorm);
    const defectLabel = resolveDefectLabel(report.damage_type);
    const imgUrl = resolveImageUrl(report.image_url);
    const dateFormatted = new Date(report.created_at).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

    // Determine ML analysis badge
    let mlSummaryBadge = '';
    if (report.ml_status === 'ML_COMPLETE' && report.detection_results && report.detection_results.length > 0) {
      const topDet = report.detection_results[0];
      const confPct = Math.round((topDet.confidence || 0) * 100);
      mlSummaryBadge = `
        <span class="badge-pill" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: var(--surface-bg);">
          AI Detected: ${confPct}% conf (${report.detection_results.length} defect${report.detection_results.length > 1 ? 's' : ''})
        </span>
      `;
    } else if (report.ml_status === 'ML_NO_DETECTIONS') {
      mlSummaryBadge = `
        <span class="badge-pill" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: var(--surface-bg); color: var(--text-muted);">
          AI: Unclassified Hazard
        </span>
      `;
    }

    // Rejection or Rework alert callout
    let cardAlertSnippet = '';
    if (statusNorm === 'rejected' && report.rejection_reason) {
      cardAlertSnippet = `
        <div style="background: rgba(239, 68, 68, 0.08); border-left: 3px solid var(--color-danger); padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.8rem; color: var(--color-danger); margin-top: 0.75rem;">
          <strong>Officer Rejection Reason:</strong> ${escapeHtml(report.rejection_reason)}
        </div>
      `;
    } else if (statusNorm === 'under_repair' && report.assigned_to) {
      cardAlertSnippet = `
        <div style="background: rgba(59, 130, 246, 0.08); border-left: 3px solid var(--accent-color); padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.75rem;">
          <strong>Field Crew Dispatched:</strong> ${escapeHtml(report.assigned_to)}
        </div>
      `;
    } else if (statusNorm === 'closed') {
      cardAlertSnippet = `
        <div style="background: rgba(34, 197, 94, 0.08); border-left: 3px solid var(--color-success); padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.8rem; color: var(--color-success); margin-top: 0.75rem;">
          &check; Municipal repair verified and officially closed.
        </div>
      `;
    }

    const locDisplay = report.address_text 
      ? escapeHtml(report.address_text) 
      : (report.latitude && report.longitude ? `${Number(report.latitude).toFixed(4)}°, ${Number(report.longitude).toFixed(4)}°` : 'Location pinned');

    return `
      <div class="assignment-card" id="card_report_${report.id}">
        <div class="assignment-card-header">
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">
              Report #${report.id}
            </span>
            <h3 class="assignment-defect-title" style="margin-top: 0.15rem;">${escapeHtml(defectLabel)}</h3>
          </div>
          <span class="status-badge status-${statusNorm}">
            <span class="status-badge-dot"></span>
            ${escapeHtml(statusLabel)}
          </span>
        </div>

        <div class="assignment-thumb-box" onclick="CivicSightMyReports.openDetailModal(${report.id})" style="cursor: pointer;" title="Click to view full inspection & timeline">
          <img src="${escapeHtml(imgUrl)}" alt="Reported damage" class="assignment-thumb-img" loading="lazy">
        </div>

        <div class="assignment-card-body">
          <div class="assignment-meta-row" style="margin-bottom: 0.5rem;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
            <span style="font-size: 0.85rem; color: var(--text-secondary);">${locDisplay}</span>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">Submitted: ${dateFormatted}</span>
            ${mlSummaryBadge}
          </div>

          ${report.description ? `
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
              "${escapeHtml(report.description)}"
            </p>
          ` : ''}

          ${cardAlertSnippet}
        </div>

        <div class="assignment-card-actions">
          <button type="button" class="btn btn-secondary btn-sm" style="width: 100%;" onclick="CivicSightMyReports.openDetailModal(${report.id})">
            Track Progress &amp; AI Analysis &rarr;
          </button>
        </div>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // 5. Deep Inspection & History Modal
  // --------------------------------------------------------------------------
  async function openDetailModal(reportId) {
    currentlyInspectedReportId = reportId;
    let report = myReports.find(r => r.id === reportId);

    // Fetch full single report detail
    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        report = await res.json();
      }
    } catch (err) {
      console.warn('Could not fetch individual report detail, falling back to cached list:', err);
    }

    if (!report) return;

    updateModalUI(report);

    if (citizenDetailModal) citizenDetailModal.classList.add('open');
  }

  async function updateModalUI(report) {
    const statusNorm = (report.status || 'submitted').toLowerCase();
    const statusLabel = formatStatusLabel(statusNorm);
    const defectLabel = resolveDefectLabel(report.damage_type);
    const dateFormatted = new Date(report.created_at).toLocaleString();

    if (modalDetailTitle) {
      modalDetailTitle.textContent = `Report #${report.id}: ${defectLabel}`;
    }
    if (modalDetailSubheader) {
      modalDetailSubheader.textContent = `Report ID #${report.id} • Submitted on ${dateFormatted}`;
    }

    if (modalDetailStatusBadge) {
      modalDetailStatusBadge.className = `status-badge status-${statusNorm}`;
    }
    if (modalDetailStatusText) {
      modalDetailStatusText.textContent = statusLabel;
    }

    // Modal Alert Banner (Rejection / Sent Back)
    if (modalAlertBanner) {
      if (statusNorm === 'rejected') {
        modalAlertBanner.style.display = 'block';
        modalAlertBanner.style.background = 'rgba(239, 68, 68, 0.1)';
        modalAlertBanner.style.border = '1px solid var(--color-danger)';
        modalAlertBanner.style.color = 'var(--color-danger)';
        modalAlertBanner.innerHTML = `
          <strong>Notice: Report Rejected by Municipal Officer</strong>
          <p style="margin: 0.35rem 0 0 0;">Reason: ${escapeHtml(report.rejection_reason || 'No specific reason provided.')}</p>
        `;
      } else {
        modalAlertBanner.style.display = 'none';
      }
    }

    // Location & Meta
    if (modalLocationText) {
      modalLocationText.textContent = report.address_text || 'San Francisco, CA';
    }
    if (modalCoordsText) {
      modalCoordsText.textContent = (report.latitude && report.longitude)
        ? `${Number(report.latitude).toFixed(6)}°, ${Number(report.longitude).toFixed(6)}°`
        : 'Coordinates unlisted';
    }
    if (modalPriorityText) {
      modalPriorityText.textContent = `${report.priority || 'MEDIUM'} Priority`;
    }
    if (modalCrewText) {
      modalCrewText.textContent = report.assigned_to 
        ? `${report.assigned_to}` 
        : 'Awaiting Municipal Officer Assignment';
    }
    if (modalDescriptionText) {
      modalDescriptionText.textContent = report.description || 'No description provided by reporter.';
    }

    // AI Viewer Slot
    if (modalMLViewerSlot && typeof CivicSightMLViewer !== 'undefined') {
      const imgUrl = resolveImageUrl(report.image_url);
      const detections = (report.detection_results || []).map(d => ({
        type: d.detected_class,
        label: d.class_name,
        confidence: d.confidence,
        bbox: d.bbox_normalized || [d.bbox_ymin, d.bbox_xmin, d.bbox_ymax, d.bbox_xmax],
        severity: d.severity,
      }));

      CivicSightMLViewer.render(modalMLViewerSlot, {
        imageUrl: imgUrl,
        mlStatus: report.ml_status || (detections.length > 0 ? 'ML_COMPLETE' : 'ML_NO_DETECTIONS'),
        detections: detections,
        latitude: report.latitude,
        longitude: report.longitude,
        address: report.address_text,
        reportId: report.id,
        modelVersion: report.ml_model_version || 'YOLOv8n-CivicSight-4Class',
        inferenceTimeMs: report.ml_inference_time_ms,
      });
    }

    // Side-by-side Before/After Photo Evidence
    const hasEvidence = report.repair_evidence && report.repair_evidence.length > 0;
    if (modalBeforeAfterWrap) {
      if (hasEvidence) {
        modalBeforeAfterWrap.style.display = 'block';
        if (modalBeforeImg) modalBeforeImg.src = resolveImageUrl(report.image_url);

        const afterPhotos = report.repair_evidence.filter(e => (e.kind || '').toUpperCase() === 'AFTER');
        if (afterPhotos.length > 0 && modalAfterImg) {
          const firstAfter = afterPhotos[0];
          const fileEndpoint = `${API_BASE}/api/v1/reports/${report.id}/evidence/${firstAfter.id}/file`;
          
          if (CivicSightAuth && CivicSightAuth.fetchAuthenticatedImageUrl) {
            CivicSightAuth.fetchAuthenticatedImageUrl(fileEndpoint).then(blobUrl => {
              if (blobUrl) modalAfterImg.src = blobUrl;
            });
          } else {
            modalAfterImg.src = fileEndpoint;
          }
        }
      } else {
        modalBeforeAfterWrap.style.display = 'none';
      }
    }

    // Chronological History Timeline
    renderTimeline(report);
  }

  function renderTimeline(report) {
    if (!modalTimeline) return;

    const historyItems = (report.status_history || report.history || []);

    if (historyItems.length === 0) {
      modalTimeline.innerHTML = `
        <div style="padding: 0.5rem 0; color: var(--text-muted); font-size: 0.85rem;">
          Initial report submitted on ${new Date(report.created_at).toLocaleString()}. Triage review in progress.
        </div>
      `;
      return;
    }

    modalTimeline.innerHTML = historyItems.map(item => {
      const dt = new Date(item.created_at || item.timestamp).toLocaleString();
      const statusLabel = formatStatusLabel(item.to_status);
      const userLabel = item.changed_by_name || 'System';

      return `
        <div class="timeline-item" style="position: relative; margin-bottom: 1.25rem;">
          <div style="position: absolute; left: -1.65rem; top: 0.25rem; width: 10px; height: 10px; border-radius: 50%; background: var(--accent-color); border: 2px solid var(--card-bg);"></div>
          <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <strong style="font-size: 0.9rem; color: var(--text-primary);">${escapeHtml(statusLabel)}</strong>
            <span style="font-size: 0.75rem; color: var(--text-muted);">${dt}</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0.25rem 0 0 0; line-height: 1.4;">
            ${escapeHtml(item.note || 'Status milestone updated.')}
          </p>
          <span style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-top: 0.2rem;">
            Updated by: ${escapeHtml(userLabel)}
          </span>
        </div>
      `;
    }).join('');
  }

  function closeDetailModal() {
    if (citizenDetailModal) citizenDetailModal.classList.remove('open');
    currentlyInspectedReportId = null;
  }

  // --------------------------------------------------------------------------
  // 6. Event Listeners & Tab Handlers
  // --------------------------------------------------------------------------
  function setupListeners() {
    refreshBtn?.addEventListener('click', () => {
      fetchMyReports(false);
      CivicSightAuth.showToast('Checking for latest status updates...', 'info');
    });

    closeDetailModalBtn?.addEventListener('click', closeDetailModal);
    closeDetailModalFooterBtn?.addEventListener('click', closeDetailModal);
    citizenDetailModal?.addEventListener('click', (e) => {
      if (e.target === citizenDetailModal) closeDetailModal();
    });

    document.querySelectorAll('.filter-tab').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTab = btn.getAttribute('data-tab') || 'all';
        renderReports();
      });
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && citizenDetailModal?.classList.contains('open')) {
        closeDetailModal();
      }
    });
  }

  // --------------------------------------------------------------------------
  // 7. Initialization
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    if (checkSession()) {
      setupListeners();
      fetchMyReports(false);

      // Background synchronization every 12 seconds
      pollingInterval = setInterval(() => {
        fetchMyReports(true);
      }, 12000);
    }
  });

  // Expose global controller for inline onclick handlers
  window.CivicSightMyReports = {
    openDetailModal: openDetailModal,
    refresh: () => fetchMyReports(false),
  };
})();
