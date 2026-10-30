/**
 * CivicSight — Reusable Visual ML Detection Results Component
 *
 * ML detection viewer:
 * - Image container with animated SVG bounding box overlays color-coded by class:
 *     * D00 (Longitudinal Crack): Sky Blue (#38bdf8)
 *     * D10 (Transverse Crack): Teal (#2dd4bf)
 *     * D20 (Alligator Crack): Amber (#f59e0b)
 *     * D40 (Pothole Hazard): Crimson (#ef4444)
 * - Results list sorted by confidence descending with defect classification
 * - Derived severity rating (HIGH / MEDIUM / LOW) based on genuine defect taxonomy
 * - Clear 4-state lifecycle handling: ML_PENDING, ML_COMPLETE, ML_NO_DETECTIONS, ML_FAILED
 * - Zero synthetic/fake bounding box generation
 * - Incident coordinates & geospatial metadata
 * - Fully theme-responsive (both light and dark modes)
 */

const CivicSightMLViewer = (() => {
  // Classification dictionary mapping standard RDD2022 codes to plain descriptions & theme colors
  const DAMAGE_TYPES = {
    D00: {
      code: 'D00',
      name: 'Longitudinal Crack',
      baseSeverity: 'MEDIUM',
      color: '#38bdf8',
      category: 'Surface Fracture',
    },
    D10: {
      code: 'D10',
      name: 'Transverse Crack',
      baseSeverity: 'MEDIUM',
      color: '#2dd4bf',
      category: 'Surface Fracture',
    },
    D20: {
      code: 'D20',
      name: 'Alligator / Fatigue Crack',
      baseSeverity: 'HIGH',
      color: '#f59e0b',
      category: 'Structural Fatigue',
    },
    D40: {
      code: 'D40',
      name: 'Pothole Hazard',
      baseSeverity: 'HIGH',
      color: '#ef4444',
      category: 'Cavity / Pavement Loss',
    },
    OTHER: {
      code: 'OTHER',
      name: 'Surface Defect',
      baseSeverity: 'LOW',
      color: '#94a3b8',
      category: 'General Wear',
    },
  };

  /**
   * Derive overall report severity rating from detected damage types and confidence
   */
  function calculateSeverity(detections) {
    if (!detections || detections.length === 0) {
      return { level: 'LOW', score: 0, label: 'Clean Surface / No Defects' };
    }

    let maxScore = 0;
    let hasD40 = false;
    let hasD20 = false;

    for (const d of detections) {
      const typeCode = (d.type || d.detected_class || '').toUpperCase();
      const conf = Math.max(0.0, Math.min(1.0, d.confidence || 0.5));

      let score = 20;
      if (typeCode === 'D40') {
        hasD40 = true;
        // Pothole: cavity hazard, score 70-88 depending on confidence
        score = Math.round(70 + conf * 18);
      } else if (typeCode === 'D20') {
        hasD20 = true;
        // Alligator crack: structural fatigue, score 55-75 depending on confidence
        score = Math.round(55 + conf * 20);
      } else if (typeCode === 'D00' || typeCode === 'D10') {
        // Linear cracks: surface fracture, score 35-55 depending on confidence
        score = Math.round(35 + conf * 20);
      } else {
        score = Math.round(20 + conf * 20);
      }

      if (score > maxScore) maxScore = score;
    }

    // Adjust for multiple detections (aggregate damage extent)
    if (detections.length > 1) {
      maxScore = Math.min(92, maxScore + (detections.length - 1) * 3);
    }

    if (maxScore >= 70 || hasD40) {
      return { level: 'HIGH', score: maxScore, label: 'High Priority Remediation' };
    } else if (maxScore >= 45 || hasD20) {
      return { level: 'MEDIUM', score: maxScore, label: 'Moderate Impact' };
    }
    return { level: 'LOW', score: maxScore, label: 'Routine Maintenance' };
  }

  /**
   * Escape HTML utility
   */
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * Render the complete ML Detection Viewer into a target container
   *
   * @param {HTMLElement|string} target - Container element or ID
   * @param {Object} options
   * @param {string} options.imageUrl - Source URL or dataURI of the damage photo
   * @param {string} [options.mlStatus] - 'ML_PENDING' | 'ML_COMPLETE' | 'ML_NO_DETECTIONS' | 'ML_FAILED'
   * @param {Array} [options.detections] - Array of { type, confidence, bbox: [ymin, xmin, ymax, xmax] } (normalized 0-1)
   * @param {number} [options.latitude] - Geolocation latitude
   * @param {number} [options.longitude] - Geolocation longitude
   * @param {string} [options.address] - Optional street or landmark address
   * @param {string|number} [options.reportId] - Optional report ID
   * @param {string} [options.modelVersion] - Identifier of YOLO model used
   * @param {number} [options.inferenceTimeMs] - Inference latency in ms
   * @param {string} [options.errorMessage] - Detailed error message if ML_FAILED
   */
  function render(target, options = {}) {
    const container = typeof target === 'string' ? document.getElementById(target) : target;
    if (!container) return;

    const {
      imageUrl,
      mlStatus: rawMlStatus,
      detections = [],
      latitude,
      longitude,
      address = 'Pinned Location',
      reportId = null,
      modelVersion = 'YOLOv8n-CivicSight-4Class',
      inferenceTimeMs = null,
      errorMessage = null,
    } = options;

    // Normalize ML status
    let mlStatus = (rawMlStatus || '').toUpperCase();
    if (!mlStatus) {
      if (detections && detections.length > 0) {
        mlStatus = 'ML_COMPLETE';
      } else {
        mlStatus = 'ML_NO_DETECTIONS';
      }
    }

    // ------------------------------------------------------------------------
    // STATE 1: ML_PENDING — Automated Analysis in Progress
    // ------------------------------------------------------------------------
    if (mlStatus === 'ML_PENDING') {
      container.innerHTML = `
        <div class="ml-viewer-card ml-card-pending" role="region" aria-label="Automated AI Analysis Pending">
          <div class="ml-viewer-header">
            <div class="ml-viewer-title-group">
              <span class="ml-status-pill">
                <span class="ml-status-dot" style="background-color: var(--accent-color);"></span>
                AI Assessment (Decision Support)
              </span>
              <h3 class="ml-viewer-title">${reportId ? `Report #${reportId} AI Triage` : 'Automated Analysis'}</h3>
            </div>
            <span class="status-badge status-pending" style="font-size: 0.75rem;">
              <span class="status-badge-dot"></span>
              ML_PENDING
            </span>
          </div>

          <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.5rem 0.85rem; margin-bottom: 1.25rem; font-size: 0.775rem; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <span><strong>Decision Support Only:</strong> AI predictions provide diagnostic guidance and do not constitute official municipal verification.</span>
          </div>

          <div style="display: flex; align-items: center; gap: 1.5rem; padding: 1rem 0.5rem;">
            <div class="lottie-wrap" style="width: 64px; height: 64px; flex-shrink: 0;">
              <lottie-player src="../assets/lottie/scanning.json" background="transparent" speed="1" loop autoplay aria-hidden="true" style="width: 64px; height: 64px;"></lottie-player>
            </div>
            <div>
              <h4 style="margin: 0 0 0.35rem 0; font-size: 1.05rem; color: var(--text-primary); font-family: var(--font-display);">Automated Analysis in Progress...</h4>
              <p style="margin: 0; font-size: 0.875rem; color: var(--text-secondary); line-height: 1.5;">
                The 4-class road defect detection pipeline is analyzing uploaded road surface imagery. Results will appear automatically upon completion.
              </p>
            </div>
          </div>
        </div>
      `;
      return;
    }

    // ------------------------------------------------------------------------
    // STATE 2: ML_NO_DETECTIONS — Clean road surface, zero damage detected
    // ------------------------------------------------------------------------
    if (mlStatus === 'ML_NO_DETECTIONS') {
      container.innerHTML = `
        <div class="ml-viewer-card ml-card-no-detections" role="region" aria-label="No Damage Detected by AI">
          <div class="ml-viewer-header">
            <div class="ml-viewer-title-group">
              <span class="ml-status-pill">
                <span class="ml-status-dot" style="background-color: var(--color-success);"></span>
                AI Assessment (Decision Support)
              </span>
              <h3 class="ml-viewer-title">${reportId ? `Report #${reportId} AI Triage` : 'Automated Analysis'}</h3>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span class="status-badge" style="font-size: 0.75rem; background: var(--color-success-bg, rgba(34,197,94,0.1)); color: var(--color-success, #16a34a); border: 1px solid var(--color-success-border, rgba(34,197,94,0.25));">
                <span class="status-badge-dot" style="background: var(--color-success, #16a34a);"></span>
                ML_NO_DETECTIONS
              </span>
              <span class="ml-severity-badge severity-low">
                <span class="severity-bullet"></span>
                <strong>CLEAR SURFACE</strong>
              </span>
            </div>
          </div>

          <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.5rem 0.85rem; margin-bottom: 1.25rem; font-size: 0.775rem; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <span><strong>Decision Support Only:</strong> AI predictions provide diagnostic guidance and do not constitute official municipal verification.</span>
            <span>Model: <code>${escapeHtml(modelVersion)}</code>${inferenceTimeMs ? ` &bull; ${Math.round(inferenceTimeMs)}ms` : ''}</span>
          </div>

          <div style="display: grid; grid-template-columns: minmax(180px, 240px) 1fr; gap: 1.5rem; align-items: center; padding: 0.5rem 0;">
            <div style="border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border-color); height: 160px; background: var(--bg-secondary);">
              <img src="${imageUrl || '../assets/test_damage.jpg'}" alt="Inspected road pavement" style="width: 100%; height: 100%; object-fit: cover; display: block;">
            </div>
            <div>
              <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-success, #16a34a)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                <h4 style="margin: 0; font-size: 1.05rem; color: var(--text-primary); font-family: var(--font-display);">No qualifying defects detected</h4>
              </div>
              <p style="margin: 0 0 0.75rem 0; font-size: 0.875rem; color: var(--text-secondary); line-height: 1.55;">
                The 4-class road damage detection model evaluated the road surface imagery and found no qualifying structural damage (D00 longitudinal cracks, D10 transverse cracks, D20 alligator cracks, or D40 potholes) exceeding detection confidence thresholds.
              </p>
              <div style="font-size: 0.8rem; color: var(--text-secondary); background: var(--bg-secondary); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); border-left: 3px solid var(--color-success, #16a34a);">
                <strong>Municipal Verification:</strong> Field personnel may still inspect and verify road condition if citizen reported concerns.
              </div>
            </div>
          </div>
        </div>
      `;
      return;
    }

    // ------------------------------------------------------------------------
    // STATE 3: ML_FAILED — Inference threw an error or timed out
    // ------------------------------------------------------------------------
    if (mlStatus === 'ML_FAILED') {
      container.innerHTML = `
        <div class="ml-viewer-card ml-card-failed" role="region" aria-label="Automated AI Analysis Unavailable">
          <div class="ml-viewer-header">
            <div class="ml-viewer-title-group">
              <span class="ml-status-pill">
                <span class="ml-status-dot" style="background-color: var(--color-danger, #ef4444);"></span>
                AI Assessment (Decision Support)
              </span>
              <h3 class="ml-viewer-title">${reportId ? `Report #${reportId} AI Triage` : 'Automated Analysis'}</h3>
            </div>
            <span class="status-badge" style="font-size: 0.75rem; background: var(--color-danger-bg, rgba(239,68,68,0.1)); color: var(--color-danger, #ef4444); border: 1px solid var(--color-danger-border, rgba(239,68,68,0.25));">
              <span class="status-badge-dot" style="background: var(--color-danger, #ef4444);"></span>
              ML_FAILED
            </span>
          </div>

          <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.5rem 0.85rem; margin-bottom: 1.25rem; font-size: 0.775rem; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <span><strong>Decision Support Only:</strong> AI predictions provide diagnostic guidance and do not constitute official municipal verification.</span>
          </div>

          <div style="display: grid; grid-template-columns: minmax(160px, 220px) 1fr; gap: 1.5rem; align-items: center; padding: 0.5rem 0;">
            ${imageUrl ? `
              <div style="border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border-color); height: 140px; background: var(--bg-secondary);">
                <img src="${imageUrl}" alt="Uploaded report photo" style="width: 100%; height: 100%; object-fit: cover; display: block;">
              </div>
            ` : ''}
            <div>
              <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger, #ef4444)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <h4 style="margin: 0; font-size: 1.05rem; color: var(--text-primary); font-family: var(--font-display);">Automated analysis could not be completed</h4>
              </div>
              <p style="margin: 0 0 0.65rem 0; font-size: 0.875rem; color: var(--text-secondary); line-height: 1.55;">
                ML inference was unable to evaluate this image (${escapeHtml(errorMessage || 'File format or inference timeout')}). <strong>The citizen report remains fully registered and valid.</strong>
              </p>
              <div style="font-size: 0.8rem; color: var(--text-secondary); background: var(--bg-secondary); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); border-left: 3px solid var(--color-danger, #ef4444);">
                <strong>Manual Review Required:</strong> Please inspect the attached photograph manually in the municipal dashboard.
              </div>
            </div>
          </div>
        </div>
      `;
      return;
    }

    // ------------------------------------------------------------------------
    // STATE 4: ML_COMPLETE — Detections present with bounding boxes & classes
    // ------------------------------------------------------------------------
    const sortedDetections = [...detections].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    const severity = calculateSeverity(sortedDetections);

    const html = `
      <div class="ml-viewer-card ml-card-complete" role="region" aria-label="AI damage detection assessment">
        <div class="ml-viewer-header">
          <div class="ml-viewer-title-group">
            <span class="ml-status-pill">
              <span class="ml-status-dot"></span>
              AI Assessment (Decision Support)
            </span>
            <h3 class="ml-viewer-title">${reportId ? `Report #${reportId} AI Triage` : 'Defect Analysis'}</h3>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="status-badge" style="font-size: 0.75rem; background: var(--accent-subtle); color: var(--accent-color); border: 1px solid var(--accent-subtle-border);">
              <span class="status-badge-dot"></span>
              ML_COMPLETE
            </span>
            <div class="ml-severity-badge severity-${severity.level.toLowerCase()}">
              <span class="severity-bullet"></span>
              <strong>${severity.level} PRIORITY (AI ESTIMATE)</strong>
            </div>
          </div>
        </div>

        <!-- Strict separation notice & model metadata -->
        <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.5rem 0.85rem; margin-bottom: 1.25rem; font-size: 0.775rem; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
          <span><strong>Decision Support Only:</strong> AI detections and severity estimates assist municipal triage and do NOT constitute official verification.</span>
          <span>Model: <code>${escapeHtml(modelVersion)}</code>${inferenceTimeMs ? ` &bull; ${Math.round(inferenceTimeMs)}ms` : ''}</span>
        </div>

        <!-- Visual Image Canvas with Animated Bounding Box Overlays -->
        <div class="ml-image-viewport">
          <div class="ml-image-wrapper" id="mlImageWrapper">
            <img src="${imageUrl || '../assets/test_damage.jpg'}" alt="Analyzed road damage surface" class="ml-analyzed-image" id="mlAnalyzedImage">
            <svg class="ml-bounding-overlay" id="mlSvgOverlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <!-- Bounding boxes injected dynamically below -->
            </svg>
          </div>
        </div>

        <!-- Severity Meter Bar -->
        <div class="ml-severity-bar-wrap">
          <div class="ml-severity-bar-header">
            <span class="severity-meter-label">AI Estimated Impact Rating</span>
            <span class="severity-meter-score">${severity.score}% · ${severity.label}</span>
          </div>
          <div class="ml-severity-track" role="progressbar" aria-valuenow="${severity.score}" aria-valuemin="0" aria-valuemax="100">
            <div class="ml-severity-fill fill-${severity.level.toLowerCase()}" style="width: ${severity.score}%;"></div>
          </div>
        </div>

        <!-- Detection Results List & Coordinates -->
        <div class="ml-details-grid">
          <!-- Detected Defects List -->
          <div class="ml-detections-pane">
            <h4 class="ml-pane-title">Classified Defects (${sortedDetections.length})</h4>
            <div class="ml-detections-list">
              ${sortedDetections.length > 0 ? sortedDetections.map((det, index) => {
                const typeCode = (det.type || det.detected_class || det.class_name || 'OTHER').toUpperCase();
                const typeInfo = DAMAGE_TYPES[typeCode] || {
                  code: typeCode,
                  name: det.label || det.class_name || 'Road Defect',
                  color: '#94a3b8',
                };
                const confPercent = Math.round((det.confidence !== undefined ? det.confidence : 0) * 100);
                return `
                  <div class="ml-detection-item" data-box-index="${index}" tabindex="0">
                    <div class="detection-item-left">
                      <span class="detection-code-chip" style="background-color: ${typeInfo.color}22; color: ${typeInfo.color}; border: 1px solid ${typeInfo.color}66;">${typeInfo.code}</span>
                      <div>
                        <strong class="detection-name">${escapeHtml(typeInfo.name)}</strong>
                        <span class="detection-model-tag" style="display: block; font-size: 0.725rem; color: var(--text-muted);">${escapeHtml(typeInfo.category || 'Road Hazard')}</span>
                      </div>
                    </div>
                    <div class="detection-confidence-wrap">
                      <span class="confidence-val" style="color: ${typeInfo.color}; font-weight: 700;">${confPercent}%</span>
                      <span class="confidence-label">Confidence</span>
                    </div>
                  </div>
                `;
              }).join('') : `
                <div class="ml-empty-detections">
                  <p>No structural hazards identified in this frame.</p>
                </div>
              `}
            </div>
          </div>

          <!-- Geolocation Coordinates Card -->
          <div class="ml-coords-pane">
            <h4 class="ml-pane-title">Geospatial Coordinates</h4>
            <div class="ml-coords-card">
              <div class="ml-coords-row">
                <span class="coord-label">Latitude:</span>
                <code class="coord-val">${latitude !== undefined ? Number(latitude).toFixed(6) : 'N/A'}</code>
              </div>
              <div class="ml-coords-row">
                <span class="coord-label">Longitude:</span>
                <code class="coord-val">${longitude !== undefined ? Number(longitude).toFixed(6) : 'N/A'}</code>
              </div>
              <div class="ml-coords-row address-row">
                <span class="coord-label">Address:</span>
                <span class="coord-address">${escapeHtml(address) || 'Verified GPS Coordinate'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Populate animated SVG bounding boxes with per-class colors
    const svgOverlay = container.querySelector('#mlSvgOverlay');
    if (svgOverlay && sortedDetections.length > 0) {
      svgOverlay.innerHTML = '';

      sortedDetections.forEach((det, idx) => {
        let x, y, w, h;
        if (det.bbox && det.bbox.length === 4) {
          if (det.bboxFormat === 'xywh') {
            [x, y, w, h] = det.bbox.map(v => v * 100);
          } else if (det.bboxFormat === 'xyxy') {
            const [xmin, ymin, xmax, ymax] = det.bbox;
            x = Math.max(0, Math.min(100, xmin * 100));
            y = Math.max(0, Math.min(100, ymin * 100));
            w = Math.max(0.5, Math.min(100 - x, (xmax - xmin) * 100));
            h = Math.max(0.5, Math.min(100 - y, (ymax - ymin) * 100));
          } else {
            // Normalized [ymin, xmin, ymax, xmax] convention
            const [ymin, xmin, ymax, xmax] = det.bbox;
            x = Math.max(0, Math.min(100, xmin * 100));
            y = Math.max(0, Math.min(100, ymin * 100));
            w = Math.max(0.5, Math.min(100 - x, (xmax - xmin) * 100));
            h = Math.max(0.5, Math.min(100 - y, (ymax - ymin) * 100));
          }
        } else {
          // Zero fake/synthetic box generation: if bbox is missing, do not draw synthetic box
          return;
        }

        const typeCode = (det.type || det.detected_class || det.class_name || 'OTHER').toUpperCase();
        const typeInfo = DAMAGE_TYPES[typeCode] || { code: typeCode, name: det.label || det.class_name || 'Defect', color: '#94a3b8' };
        const boxColor = typeInfo.color || '#38bdf8';
        const confPercent = Math.round((det.confidence !== undefined ? det.confidence : 0) * 100);

        // Create SVG Group
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', `bbox-group bbox-group-${idx}`);
        g.setAttribute('data-index', idx);

        // Animated Rectangle Box
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', w);
        rect.setAttribute('height', h);
        rect.setAttribute('rx', '1.5');
        rect.setAttribute('class', 'bbox-rect');
        rect.style.stroke = boxColor;
        rect.style.fill = `${boxColor}18`;
        rect.style.animationDelay = `${idx * 0.15}s`;

        // Corner bracket accents
        const cornerSize = Math.min(w, h) * 0.25;
        const cornerPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        cornerPath.setAttribute('d', `
          M ${x} ${y + cornerSize} L ${x} ${y} L ${x + cornerSize} ${y}
          M ${x + w - cornerSize} ${y} L ${x + w} ${y} L ${x + w} ${y + cornerSize}
          M ${x + w} ${y + h - cornerSize} L ${x + w} ${y + h} L ${x + w - cornerSize} ${y + h}
          M ${x + cornerSize} ${y + h} L ${x} ${y + h} L ${x} ${y + h - cornerSize}
        `);
        cornerPath.setAttribute('class', 'bbox-corners');
        cornerPath.style.stroke = boxColor;
        cornerPath.style.animationDelay = `${idx * 0.15 + 0.1}s`;

        // Tag label above or inside the box
        const labelY = Math.max(y - 1, 4.5);
        const tagGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        tagGroup.setAttribute('class', 'bbox-tag-group');
        tagGroup.style.animationDelay = `${idx * 0.15 + 0.2}s`;

        const tagBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        tagBg.setAttribute('x', x);
        tagBg.setAttribute('y', labelY - 4.2);
        tagBg.setAttribute('width', Math.min(w, 30));
        tagBg.setAttribute('height', 4.2);
        tagBg.setAttribute('rx', '0.8');
        tagBg.setAttribute('class', 'bbox-tag-bg');
        tagBg.style.fill = boxColor;

        const tagText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        tagText.setAttribute('x', x + 1);
        tagText.setAttribute('y', labelY - 1.2);
        tagText.setAttribute('class', 'bbox-tag-text');
        tagText.style.fill = '#ffffff';
        tagText.style.fontSize = '3px';
        tagText.style.fontWeight = 'bold';
        tagText.textContent = `${typeInfo.code} ${confPercent}%`;

        tagGroup.appendChild(tagBg);
        tagGroup.appendChild(tagText);

        g.appendChild(rect);
        g.appendChild(cornerPath);
        g.appendChild(tagGroup);
        svgOverlay.appendChild(g);
      });

      // Hover linkage between list items and bounding boxes
      container.querySelectorAll('.ml-detection-item').forEach(item => {
        const idx = item.getAttribute('data-box-index');
        const boxGroup = svgOverlay.querySelector(`.bbox-group-${idx}`);

        item.addEventListener('mouseenter', () => {
          boxGroup?.classList.add('highlight-active');
        });
        item.addEventListener('mouseleave', () => {
          boxGroup?.classList.remove('highlight-active');
        });
      });
    }
  }

  return {
    render,
    calculateSeverity,
    DAMAGE_TYPES,
  };
})();

// Attach globally
window.CivicSightMLViewer = CivicSightMLViewer;
