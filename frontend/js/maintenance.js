/**
 * CivicSight - Maintenance Staff Field Portal Logic
 * 
 * Strict Role-Based Access: Maintenance Staff and Admin only.
 * Full Repair Lifecycle:
 *  1. ASSIGNED -> Start Repair -> UNDER_REPAIR
 *  2. UNDER_REPAIR -> Upload AFTER Evidence Photos -> POST /reports/{id}/repair/evidence
 *  3. UNDER_REPAIR -> Submit for Verification -> REPAIR_EVIDENCE_SUBMITTED
 *  4. Review Sent-Back Rework Instructions
 *  5. Inspect Side-by-Side Before/After Photo Evidence
 */

(function() {
  'use strict';

  const API_BASE = window.location.origin.includes(':3000') || window.location.origin.includes(':8080')
    ? 'http://127.0.0.1:8000'
    : '';

  // DOM Elements
  const staffUserName = document.getElementById('staffUserName');
  const statActiveCount = document.getElementById('statActiveCount');
  const statCompletedCount = document.getElementById('statCompletedCount');
  const tabActiveBtn = document.getElementById('tabActiveBtn');
  const tabCompletedBtn = document.getElementById('tabCompletedBtn');
  const assignmentsLoading = document.getElementById('assignmentsLoading');
  const assignmentsEmpty = document.getElementById('assignmentsEmpty');
  const assignmentsGrid = document.getElementById('assignmentsGrid');
  const refreshAssignmentsBtn = document.getElementById('refreshAssignmentsBtn');

  // Evidence Modal Elements
  const evidenceModal = document.getElementById('evidenceModal');
  const closeEvidenceModalBtn = document.getElementById('closeEvidenceModalBtn');
  const closeEvidenceModalFooterBtn = document.getElementById('closeEvidenceModalFooterBtn');
  const evidenceModalReportBadge = document.getElementById('evidenceModalReportBadge');
  const evidenceModalBeforeThumb = document.getElementById('evidenceModalBeforeThumb');
  const evidenceModalDefectTitle = document.getElementById('evidenceModalDefectTitle');
  const evidenceModalLocation = document.getElementById('evidenceModalLocation');
  const evidenceDropzone = document.getElementById('evidenceDropzone');
  const evidenceFileInput = document.getElementById('evidenceFileInput');
  const evidenceSelectedPreviewWrap = document.getElementById('evidenceSelectedPreviewWrap');
  const evidenceSelectedThumb = document.getElementById('evidenceSelectedThumb');
  const evidenceSelectedFilename = document.getElementById('evidenceSelectedFilename');
  const evidenceSelectedFilesize = document.getElementById('evidenceSelectedFilesize');
  const evidenceClearFileBtn = document.getElementById('evidenceClearFileBtn');
  const evidenceUploadNote = document.getElementById('evidenceUploadNote');
  const uploadEvidenceOnlyBtn = document.getElementById('uploadEvidenceOnlyBtn');
  const evidenceGalleryList = document.getElementById('evidenceGalleryList');
  const evidenceCountBadge = document.getElementById('evidenceCountBadge');
  const submitForVerificationBtn = document.getElementById('submitForVerificationBtn');

  // Comparison Modal Elements
  const comparisonModal = document.getElementById('comparisonModal');
  const closeComparisonModalBtn = document.getElementById('closeComparisonModalBtn');
  const closeComparisonModalBottomBtn = document.getElementById('closeComparisonModalBottomBtn');
  const comparisonBeforeImg = document.getElementById('comparisonBeforeImg');
  const comparisonBeforeMeta = document.getElementById('comparisonBeforeMeta');
  const comparisonAfterImg = document.getElementById('comparisonAfterImg');
  const comparisonAfterMeta = document.getElementById('comparisonAfterMeta');
  const comparisonThumbs = document.getElementById('comparisonThumbs');

  // State
  let currentTab = 'active'; // 'active' | 'completed'
  let activeAssignments = [];
  let completedAssignments = [];
  let currentModalReportId = null;
  let selectedEvidenceFile = null;

  // --------------------------------------------------------------------------
  // Role & Session Guard
  // --------------------------------------------------------------------------
  function verifyStaffAccess() {
    if (!CivicSightAuth.isAuthenticated()) {
      window.location.href = 'login.html';
      return false;
    }
    const user = CivicSightAuth.getUser();
    if (!CivicSightAuth.hasRole(['Maintenance Staff', 'Admin'])) {
      CivicSightAuth.showToast('Access restricted: Maintenance Staff credentials required.', 'error');
      setTimeout(() => {
        window.location.href = user && user.role === 'Municipal Officer' ? 'dashboard.html' : 'report.html';
      }, 1200);
      return false;
    }
    if (staffUserName && user) {
      staffUserName.textContent = `${user.name} (${user.role})`;
    }
    return true;
  }

  function getAuthHeaders() {
    const token = CivicSightAuth.getToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json'
    };
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatStatusLabel(status) {
    if (!status) return 'Unknown';
    switch (status.toLowerCase()) {
      case 'submitted': return 'Submitted';
      case 'pending_verification': return 'Pending Verification';
      case 'verified': return 'Verified';
      case 'assigned': return 'Assigned';
      case 'under_repair': return 'Under Repair';
      case 'repair_evidence_submitted': return 'Evidence Submitted';
      case 'closed': return 'Closed / Fixed';
      case 'rejected': return 'Rejected';
      case 'duplicate': return 'Duplicate';
      default: return status.replace(/_/g, ' ');
    }
  }

  function renderStatusBadge(status) {
    const s = (status || 'submitted').toLowerCase();
    return `
      <span class="status-badge status-${s}">
        <span class="status-badge-dot"></span>
        <span>${escapeHtml(formatStatusLabel(s))}</span>
      </span>
    `;
  }

  function renderPriorityBadge(priority) {
    const p = (priority || 'LOW').toUpperCase();
    const dotClass = p === 'HIGH' ? 'red' : p === 'MEDIUM' ? 'amber' : 'green';
    return `
      <span class="badge-pill" style="font-size: 0.75rem; text-transform: uppercase;">
        <span class="legend-dot ${dotClass}"></span>
        ${p}
      </span>
    `;
  }

  // --------------------------------------------------------------------------
  // Data Fetching
  // --------------------------------------------------------------------------
  async function loadAssignments() {
    if (assignmentsLoading) assignmentsLoading.style.display = 'block';
    if (assignmentsEmpty) assignmentsEmpty.style.display = 'none';
    if (assignmentsGrid) assignmentsGrid.style.display = 'none';

    try {
      const [resActive, resCompleted] = await Promise.all([
        fetch(`${API_BASE}/api/v1/staff/me/assignments?view=active`, { headers: getAuthHeaders() }),
        fetch(`${API_BASE}/api/v1/staff/me/assignments?view=completed`, { headers: getAuthHeaders() })
      ]);

      if (!resActive.ok || !resCompleted.ok) {
        throw new Error('Failed to fetch assigned work orders from server.');
      }

      activeAssignments = await resActive.json();
      completedAssignments = await resCompleted.json();

      if (statActiveCount) statActiveCount.textContent = activeAssignments.length;
      if (statCompletedCount) statCompletedCount.textContent = completedAssignments.length;

      renderCurrentTab();
    } catch (err) {
      console.error('Error loading assignments:', err);
      if (assignmentsLoading) assignmentsLoading.style.display = 'none';
      CivicSightAuth.showToast('Unable to connect to field service endpoints.', 'error');
    }
  }

  function renderCurrentTab() {
    if (assignmentsLoading) assignmentsLoading.style.display = 'none';
    const list = currentTab === 'active' ? activeAssignments : completedAssignments;

    if (!list || list.length === 0) {
      if (assignmentsEmpty) assignmentsEmpty.style.display = 'block';
      if (assignmentsGrid) assignmentsGrid.style.display = 'none';
      return;
    }

    if (assignmentsEmpty) assignmentsEmpty.style.display = 'none';
    if (assignmentsGrid) {
      assignmentsGrid.style.display = 'grid';
      assignmentsGrid.innerHTML = list.map(report => renderCard(report)).join('');
    }
  }

  function renderCard(report) {
    const status = (report.status || '').toLowerCase();
    const isSentBack = report.final_verifications && report.final_verifications.some(v => v.decision === 'SENT_BACK');
    const latestSentBack = isSentBack 
      ? [...report.final_verifications].filter(v => v.decision === 'SENT_BACK').pop() 
      : null;

    const imgUrl = report.image_path ? `${API_BASE}/${report.image_path}` : '../assets/logo-icon.png';
    const locText = (report.latitude && report.longitude)
      ? `${Number(report.latitude).toFixed(4)}°, ${Number(report.longitude).toFixed(4)}°`
      : 'Coordinates unlisted';

    let actionButtonsHtml = '';

    if (status === 'assigned') {
      actionButtonsHtml = `
        <button type="button" class="btn btn-primary btn-sm" onclick="CivicSightMaintenance.startRepair(${report.id})">
          Start Physical Repair &rarr;
        </button>
      `;
    } else if (status === 'under_repair') {
      actionButtonsHtml = `
        <button type="button" class="btn btn-primary btn-sm" onclick="CivicSightMaintenance.openEvidenceModal(${report.id})">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
          Upload Evidence &amp; Submit
        </button>
      `;
    } else if (status === 'repair_evidence_submitted') {
      actionButtonsHtml = `
        <button type="button" class="btn btn-secondary btn-sm" onclick="CivicSightMaintenance.openComparisonModal(${report.id})">
          Review Submitted Evidence
        </button>
      `;
    } else if (status === 'closed') {
      actionButtonsHtml = `
        <button type="button" class="btn btn-secondary btn-sm" onclick="CivicSightMaintenance.openComparisonModal(${report.id})">
          View Before/After
        </button>
      `;
    }

    return `
      <div class="assignment-card ${isSentBack && status === 'under_repair' ? 'is-sent-back' : ''}" id="assignmentCard_${report.id}">
        <div class="assignment-card-header">
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">
              Work Order #${report.id}
            </span>
            <h3 class="assignment-defect-title">${escapeHtml(report.defect_type || 'Road Damage')}</h3>
          </div>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            ${renderPriorityBadge(report.priority)}
            ${renderStatusBadge(status)}
          </div>
        </div>

        <div class="assignment-thumb-box" onclick="CivicSightMaintenance.openComparisonModal(${report.id})" style="cursor: pointer;" title="Click to view full photo">
          <img src="${escapeHtml(imgUrl)}" alt="Citizen initial hazard photo" class="assignment-thumb-img" loading="lazy">
        </div>

        <div class="assignment-card-body">
          <div class="assignment-meta-row">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
            <span>${escapeHtml(locText)}</span>
          </div>

          ${report.description ? `
            <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">
              <strong>Citizen Note:</strong> "${escapeHtml(report.description)}"
            </div>
          ` : ''}

          ${report.assignments && report.assignments.length > 0 && report.assignments[0].note ? `
            <div class="assignment-officer-note">
              <strong>Officer Instruction:</strong> ${escapeHtml(report.assignments[0].note)}
            </div>
          ` : ''}

          ${latestSentBack && status === 'under_repair' ? `
            <div class="assignment-rework-banner">
              <strong>Rework Required:</strong> ${escapeHtml(latestSentBack.note || 'Verification officer requested corrections.')}
            </div>
          ` : ''}
        </div>

        <div class="assignment-card-actions">
          ${actionButtonsHtml}
        </div>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // Repair Progression Actions
  // --------------------------------------------------------------------------
  async function startRepair(reportId) {
    if (!confirm(`Confirm starting field repair for Work Order #${reportId}?`)) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/repair/start`, {
        method: 'POST',
        headers: getAuthHeaders()
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        CivicSightAuth.showToast(errorData.detail || `Failed to start repair (${res.status})`, 'error');
        return;
      }

      CivicSightAuth.showToast(`Repair started on Work Order #${reportId}. Status: Under Repair.`, 'success');
      await loadAssignments();
      openEvidenceModal(reportId);
    } catch (err) {
      console.error('Error starting repair:', err);
      CivicSightAuth.showToast('Network error while starting repair.', 'error');
    }
  }

  // --------------------------------------------------------------------------
  // Evidence Modal Logic
  // --------------------------------------------------------------------------
  async function openEvidenceModal(reportId) {
    currentModalReportId = reportId;
    const report = activeAssignments.find(r => r.id === reportId) || completedAssignments.find(r => r.id === reportId);
    if (!report) return;

    if (evidenceModalReportBadge) evidenceModalReportBadge.textContent = `Work Order #${report.id}`;
    if (evidenceModalBeforeThumb) {
      evidenceModalBeforeThumb.src = report.image_path ? `${API_BASE}/${report.image_path}` : '../assets/logo-icon.png';
    }
    if (evidenceModalDefectTitle) evidenceModalDefectTitle.textContent = report.defect_type || 'Road Damage';
    if (evidenceModalLocation) {
      evidenceModalLocation.textContent = (report.latitude && report.longitude)
        ? `${Number(report.latitude).toFixed(4)}°, ${Number(report.longitude).toFixed(4)}°`
        : 'Coordinates unlisted';
    }

    clearEvidenceFileInput();
    if (evidenceModal) evidenceModal.classList.add('open');
    await loadEvidenceGallery(reportId);
  }

  function closeEvidenceModal() {
    if (evidenceModal) evidenceModal.classList.remove('open');
    currentModalReportId = null;
    clearEvidenceFileInput();
  }

  function clearEvidenceFileInput() {
    selectedEvidenceFile = null;
    if (evidenceFileInput) evidenceFileInput.value = '';
    if (evidenceSelectedPreviewWrap) evidenceSelectedPreviewWrap.style.display = 'none';
    if (evidenceDropzone) evidenceDropzone.style.display = 'block';
    if (evidenceUploadNote) evidenceUploadNote.value = '';
  }

  async function loadEvidenceGallery(reportId) {
    if (!evidenceGalleryList) return;
    evidenceGalleryList.innerHTML = `<div style="font-size: 0.825rem; color: var(--text-muted);">Loading evidence...</div>`;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/evidence`, {
        headers: getAuthHeaders()
      });

      if (!res.ok) throw new Error('Evidence fetch failed');
      const data = await res.json();
      const photos = data.evidence_photos || [];
      const afterPhotos = photos.filter(p => (p.kind || '').toUpperCase() === 'AFTER');

      if (evidenceCountBadge) evidenceCountBadge.textContent = photos.length;
      if (submitForVerificationBtn) {
        submitForVerificationBtn.disabled = afterPhotos.length === 0;
      }

      if (photos.length === 0) {
        evidenceGalleryList.innerHTML = `<div style="font-size: 0.825rem; color: var(--text-muted);">No evidence photos uploaded yet.</div>`;
        return;
      }

      evidenceGalleryList.innerHTML = photos.map(p => {
        const fileUrl = `${API_BASE}/api/v1/reports/${reportId}/evidence/${p.id}/file`;
        return `
          <div class="evidence-preview-item" title="${escapeHtml(p.note || p.kind)}">
            <img src="${escapeHtml(fileUrl)}" alt="${escapeHtml(p.kind)} Photo" onerror="this.src='${API_BASE}/${p.file_path}'">
            <span style="position: absolute; bottom: 2px; left: 2px; background: rgba(0,0,0,0.65); color: #fff; font-size: 9px; padding: 1px 4px; border-radius: 2px;">
              ${escapeHtml(p.kind)}
            </span>
          </div>
        `;
      }).join('');
    } catch (err) {
      console.error('Error loading gallery:', err);
      evidenceGalleryList.innerHTML = `<div style="font-size: 0.825rem; color: var(--color-danger);">Unable to load evidence history.</div>`;
    }
  }

  async function uploadEvidencePhoto(onlyUpload = true) {
    if (!currentModalReportId) return false;
    if (!selectedEvidenceFile) {
      CivicSightAuth.showToast('Please select a photo of the completed repair.', 'error');
      return false;
    }

    const formData = new FormData();
    formData.append('photo', selectedEvidenceFile);
    formData.append('kind', 'AFTER');
    const note = evidenceUploadNote ? evidenceUploadNote.value.trim() : '';
    if (note) formData.append('note', note);

    try {
      const token = CivicSightAuth.getToken();
      const res = await fetch(`${API_BASE}/api/v1/reports/${currentModalReportId}/repair/evidence`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        CivicSightAuth.showToast(errorData.detail || `Upload failed (${res.status})`, 'error');
        return false;
      }

      CivicSightAuth.showToast('Repair evidence photo uploaded successfully.', 'success');
      clearEvidenceFileInput();
      await loadEvidenceGallery(currentModalReportId);
      return true;
    } catch (err) {
      console.error('Error uploading photo:', err);
      CivicSightAuth.showToast('Network error during photo upload.', 'error');
      return false;
    }
  }

  async function submitForVerification() {
    if (!currentModalReportId) return;
    const note = evidenceUploadNote ? evidenceUploadNote.value.trim() : '';

    if (!confirm('Submit this completed repair for final municipal officer inspection?')) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${currentModalReportId}/repair/submit`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ note: note || null })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        CivicSightAuth.showToast(errorData.detail || `Submission failed (${res.status})`, 'error');
        return;
      }

      CivicSightAuth.showToast(`Work Order #${currentModalReportId} submitted for municipal verification!`, 'success');
      closeEvidenceModal();
      await loadAssignments();
    } catch (err) {
      console.error('Error submitting repair:', err);
      CivicSightAuth.showToast('Network error submitting repair.', 'error');
    }
  }

  // --------------------------------------------------------------------------
  // Comparison Modal Logic
  // --------------------------------------------------------------------------
  async function openComparisonModal(reportId) {
    const report = activeAssignments.find(r => r.id === reportId) || completedAssignments.find(r => r.id === reportId);
    if (!report) return;

    if (comparisonBeforeImg) {
      comparisonBeforeImg.src = report.image_path ? `${API_BASE}/${report.image_path}` : '../assets/logo-icon.png';
    }
    if (comparisonBeforeMeta) {
      comparisonBeforeMeta.innerHTML = `
        <strong>Hazard:</strong> ${escapeHtml(report.defect_type || 'Road Damage')}<br>
        <strong>Reported:</strong> ${new Date(report.created_at).toLocaleString()}<br>
        <strong>Status:</strong> ${formatStatusLabel(report.status)}
      `;
    }

    if (comparisonAfterImg) {
      comparisonAfterImg.src = '';
    }
    if (comparisonThumbs) comparisonThumbs.innerHTML = '';
    if (comparisonAfterMeta) comparisonAfterMeta.textContent = 'Loading evidence...';

    if (comparisonModal) comparisonModal.classList.add('open');

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${reportId}/evidence`, {
        headers: getAuthHeaders()
      });

      if (!res.ok) throw new Error('Evidence fetch failed');
      const data = await res.json();
      const photos = data.evidence_photos || [];
      const afterPhotos = photos.filter(p => (p.kind || '').toUpperCase() === 'AFTER');

      if (afterPhotos.length === 0) {
        if (comparisonAfterMeta) comparisonAfterMeta.textContent = 'No AFTER photos uploaded yet.';
        return;
      }

      const primary = afterPhotos[0];
      const primaryUrl = `${API_BASE}/api/v1/reports/${reportId}/evidence/${primary.id}/file`;
      if (comparisonAfterImg) comparisonAfterImg.src = primaryUrl;
      if (comparisonAfterMeta) {
        comparisonAfterMeta.innerHTML = `
          <strong>Uploaded:</strong> ${new Date(primary.uploaded_at).toLocaleString()}<br>
          <strong>Technician Note:</strong> ${escapeHtml(primary.note || 'None logged')}
        `;
      }

      if (comparisonThumbs && afterPhotos.length > 1) {
        comparisonThumbs.innerHTML = afterPhotos.map((p, idx) => {
          const thumbUrl = `${API_BASE}/api/v1/reports/${reportId}/evidence/${p.id}/file`;
          return `
            <img src="${escapeHtml(thumbUrl)}" class="evidence-gallery-thumb ${idx === 0 ? 'selected' : ''}" 
                 onclick="CivicSightMaintenance.selectComparisonThumb('${escapeHtml(thumbUrl)}', '${escapeHtml(p.note || '')}', '${p.uploaded_at}', this)">
          `;
        }).join('');
      }
    } catch (err) {
      console.error('Error fetching comparison evidence:', err);
      if (comparisonAfterMeta) comparisonAfterMeta.textContent = 'Unable to load evidence images.';
    }
  }

  function selectComparisonThumb(url, note, uploadedAt, thumbEl) {
    if (comparisonAfterImg) comparisonAfterImg.src = url;
    if (comparisonAfterMeta) {
      comparisonAfterMeta.innerHTML = `
        <strong>Uploaded:</strong> ${new Date(uploadedAt).toLocaleString()}<br>
        <strong>Technician Note:</strong> ${escapeHtml(note || 'None logged')}
      `;
    }
    document.querySelectorAll('.evidence-gallery-thumb').forEach(t => t.classList.remove('selected'));
    if (thumbEl) thumbEl.classList.add('selected');
  }

  function closeComparisonModal() {
    if (comparisonModal) comparisonModal.classList.remove('open');
  }

  // --------------------------------------------------------------------------
  // Event Listeners Initialization
  // --------------------------------------------------------------------------
  function setupEventListeners() {
    tabActiveBtn?.addEventListener('click', () => {
      currentTab = 'active';
      tabActiveBtn.classList.add('active');
      tabCompletedBtn?.classList.remove('active');
      renderCurrentTab();
    });

    tabCompletedBtn?.addEventListener('click', () => {
      currentTab = 'completed';
      tabCompletedBtn.classList.add('active');
      tabActiveBtn?.classList.remove('active');
      renderCurrentTab();
    });

    refreshAssignmentsBtn?.addEventListener('click', () => {
      loadAssignments();
      CivicSightAuth.showToast('Refreshing assigned work orders...', 'info');
    });

    // Evidence Dropzone Events
    evidenceDropzone?.addEventListener('click', () => {
      evidenceFileInput?.click();
    });

    evidenceDropzone?.addEventListener('dragover', (e) => {
      e.preventDefault();
      evidenceDropzone.classList.add('drag-over');
    });

    evidenceDropzone?.addEventListener('dragleave', () => {
      evidenceDropzone.classList.remove('drag-over');
    });

    evidenceDropzone?.addEventListener('drop', (e) => {
      e.preventDefault();
      evidenceDropzone.classList.remove('drag-over');
      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });

    evidenceFileInput?.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });

    evidenceClearFileBtn?.addEventListener('click', clearEvidenceFileInput);
    uploadEvidenceOnlyBtn?.addEventListener('click', () => uploadEvidencePhoto(true));
    submitForVerificationBtn?.addEventListener('click', submitForVerification);

    closeEvidenceModalBtn?.addEventListener('click', closeEvidenceModal);
    closeEvidenceModalFooterBtn?.addEventListener('click', closeEvidenceModal);
    evidenceModal?.addEventListener('click', (e) => {
      if (e.target === evidenceModal) closeEvidenceModal();
    });

    closeComparisonModalBtn?.addEventListener('click', closeComparisonModal);
    closeComparisonModalBottomBtn?.addEventListener('click', closeComparisonModal);
    comparisonModal?.addEventListener('click', (e) => {
      if (e.target === comparisonModal) closeComparisonModal();
    });
  }

  function handleFileSelect(file) {
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type.toLowerCase())) {
      CivicSightAuth.showToast('Invalid format. Please select JPEG, PNG, or WebP.', 'error');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      CivicSightAuth.showToast('File exceeds 15MB limit.', 'error');
      return;
    }

    selectedEvidenceFile = file;
    if (evidenceSelectedFilename) evidenceSelectedFilename.textContent = file.name;
    if (evidenceSelectedFilesize) evidenceSelectedFilesize.textContent = `${(file.size / 1024).toFixed(1)} KB`;

    const reader = new FileReader();
    reader.onload = (e) => {
      if (evidenceSelectedThumb) evidenceSelectedThumb.src = e.target.result;
      if (evidenceDropzone) evidenceDropzone.style.display = 'none';
      if (evidenceSelectedPreviewWrap) evidenceSelectedPreviewWrap.style.display = 'flex';
    };
    reader.readAsDataURL(file);
  }

  // --------------------------------------------------------------------------
  // Initialization on DOM Ready
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    if (verifyStaffAccess()) {
      setupEventListeners();
      loadAssignments();
    }
  });

  // Global namespace for inline onclick handlers
  window.CivicSightMaintenance = {
    startRepair,
    openEvidenceModal,
    openComparisonModal,
    selectComparisonThumb
  };

})();

