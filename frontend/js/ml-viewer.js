/**
 * CivicSight — Reusable Visual ML Detection Results Component
 *
 * Implements Requirement 4:
 * - Image container with animated SVG bounding box overlays in --accent-color
 * - Results list sorted by confidence descending with defect classification
 * - Derived severity rating (HIGH / MEDIUM / LOW) with visual indicator bar
 * - Incident coordinates & geospatial metadata
 * - Fully theme-responsive (both light and dark modes)
 */

const CivicSightMLViewer = (() => {
  // Classification dictionary mapping standard RDD2022 codes to plain descriptions
  const DAMAGE_TYPES = {
    D00: { code: 'D00', name: 'Longitudinal Crack', baseSeverity: 'MEDIUM' },
    D10: { code: 'D10', name: 'Transverse Crack', baseSeverity: 'MEDIUM' },
    D20: { code: 'D20', name: 'Alligator / Fatigue Crack', baseSeverity: 'HIGH' },
    D40: { code: 'D40', name: 'Pothole Hazard', baseSeverity: 'HIGH' },
    OTHER: { code: 'OTHER', name: 'Surface Defect', baseSeverity: 'LOW' },
  };

  /**
   * Derive overall report severity rating from detected damage types and confidence
   */
  function calculateSeverity(detections) {
    if (!detections || detections.length === 0) {
      return { level: 'LOW', score: 25, label: 'Low Severity' };
    }

    let maxScore = 0;
    for (const d of detections) {
      const typeInfo = DAMAGE_TYPES[d.type] || DAMAGE_TYPES.OTHER;
      const conf = d.confidence || 0.5;

      let score = 30;
      if (typeInfo.code === 'D40') {
        score = conf >= 0.8 ? 95 : 85; // Potholes are inherently high-impact
      } else if (typeInfo.code === 'D20') {
        score = conf >= 0.75 ? 80 : 70;
      } else if (typeInfo.code === 'D00' || typeInfo.code === 'D10') {
        score = conf >= 0.8 ? 65 : 50;
      }

      if (score > maxScore) maxScore = score;
    }

    if (maxScore >= 75) {
      return { level: 'HIGH', score: maxScore, label: 'High Priority Remediation' };
    } else if (maxScore >= 50) {
      return { level: 'MEDIUM', score: maxScore, label: 'Moderate Impact' };
    }
    return { level: 'LOW', score: maxScore, label: 'Routine Maintenance' };
  }

  /**
   * Render the complete ML Detection Viewer into a target container
   *
   * @param {HTMLElement|string} target - Container element or ID
   * @param {Object} options
   * @param {string} options.imageUrl - Source URL or dataURI of the damage photo
   * @param {Array} options.detections - Array of { type, confidence, bbox: [ymin, xmin, ymax, xmax] } (normalized 0-1)
   * @param {number} options.latitude - Geolocation latitude
   * @param {number} options.longitude - Geolocation longitude
   * @param {string} [options.address] - Optional street or landmark address
   * @param {string|number} [options.reportId] - Optional report ID
   */
  function render(target, options) {
    const container = typeof target === 'string' ? document.getElementById(target) : target;
    if (!container) return;

    const {
      imageUrl,
      detections = [],
      latitude,
      longitude,
      address = 'Pinned Location',
      reportId = null,
    } = options;

    // Sort detections by confidence descending
    const sortedDetections = [...detections].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    const severity = calculateSeverity(sortedDetections);

    // Build markup
    const html = `
      <div class="ml-viewer-card" role="region" aria-label="Automated AI Damage Assessment">
        <div class="ml-viewer-header">
          <div class="ml-viewer-title-group">
            <span class="ml-status-pill">
              <span class="ml-status-dot"></span>
              YOLOv8 Road Defect Detection
            </span>
            <h3 class="ml-viewer-title">${reportId ? `Report #${reportId} Analysis` : 'Automated Defect Segmentation'}</h3>
          </div>
          <div class="ml-severity-badge severity-${severity.level.toLowerCase()}">
            <span class="severity-bullet"></span>
            <strong>${severity.level} PRIORITY</strong>
          </div>
        </div>

        <!-- Visual Image Canvas with Animated Bounding Box Overlays -->
        <div class="ml-image-viewport">
          <div class="ml-image-wrapper" id="mlImageWrapper">
            <img src="${imageUrl}" alt="Analyzed road damage surface" class="ml-analyzed-image" id="mlAnalyzedImage">
            <svg class="ml-bounding-overlay" id="mlSvgOverlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <!-- Bounding boxes injected dynamically below -->
            </svg>
          </div>
        </div>

        <!-- Severity Meter Bar -->
        <div class="ml-severity-bar-wrap">
          <div class="ml-severity-bar-header">
            <span class="severity-meter-label">Damage Impact Rating</span>
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
                const typeInfo = DAMAGE_TYPES[det.type] || { code: det.type, name: det.label || 'Road Defect' };
                const confPercent = Math.round((det.confidence || 0) * 100);
                return `
                  <div class="ml-detection-item" data-box-index="${index}" tabindex="0">
                    <div class="detection-item-left">
                      <span class="detection-code-chip">${typeInfo.code}</span>
                      <div>
                        <strong class="detection-name">${typeInfo.name}</strong>
                        <span class="detection-model-tag">RDD2022 Benchmark</span>
                      </div>
                    </div>
                    <div class="detection-confidence-wrap">
                      <span class="confidence-val">${confPercent}%</span>
                      <span class="confidence-label">Confidence</span>
                    </div>
                  </div>
                `;
              }).join('') : `
                <div class="ml-empty-detections">
                  <p>No critical structural hazards identified in this frame.</p>
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
                <span class="coord-address">${address || 'Verified GPS Coordinate'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Populate animated SVG bounding boxes
    const svgOverlay = container.querySelector('#mlSvgOverlay');
    if (svgOverlay && sortedDetections.length > 0) {
      svgOverlay.innerHTML = '';

      sortedDetections.forEach((det, idx) => {
        // det.bbox: [ymin, xmin, ymax, xmax] in normalized coordinates (0 to 1) or [x, y, w, h]
        let x, y, w, h;
        if (det.bbox && det.bbox.length === 4) {
          if (det.bboxFormat === 'xywh') {
            [x, y, w, h] = det.bbox.map(v => v * 100);
          } else {
            // Default ymin, xmin, ymax, xmax
            const [ymin, xmin, ymax, xmax] = det.bbox;
            x = xmin * 100;
            y = ymin * 100;
            w = (xmax - xmin) * 100;
            h = (ymax - ymin) * 100;
          }
        } else {
          // Standard center placement fallback
          x = 20 + (idx * 15);
          y = 25 + (idx * 10);
          w = 40;
          h = 35;
        }

        const typeInfo = DAMAGE_TYPES[det.type] || { code: det.type, name: 'Defect' };
        const confPercent = Math.round((det.confidence || 0.9) * 100);

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
        // Add animation delay based on index
        rect.style.animationDelay = `${idx * 0.25}s`;

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
        cornerPath.style.animationDelay = `${idx * 0.25 + 0.15}s`;

        // Tag label above or inside the box
        const labelY = Math.max(y - 2, 4);
        const tagGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        tagGroup.setAttribute('class', 'bbox-tag-group');
        tagGroup.style.animationDelay = `${idx * 0.25 + 0.3}s`;

        const tagBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        tagBg.setAttribute('x', x);
        tagBg.setAttribute('y', labelY - 4.5);
        tagBg.setAttribute('width', Math.min(w, 32));
        tagBg.setAttribute('height', 4.5);
        tagBg.setAttribute('rx', '0.8');
        tagBg.setAttribute('class', 'bbox-tag-bg');

        const tagText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        tagText.setAttribute('x', x + 1);
        tagText.setAttribute('y', labelY - 1.2);
        tagText.setAttribute('class', 'bbox-tag-text');
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

  /**
   * Helper to simulate or synthesize detections from an image when live backend ML is offline
   */
  function generateSyntheticDetections(damageTypeHint = 'D40') {
    if (damageTypeHint === 'D40') {
      return [
        { type: 'D40', confidence: 0.948, bbox: [0.38, 0.28, 0.72, 0.68] },
        { type: 'D20', confidence: 0.814, bbox: [0.65, 0.60, 0.88, 0.85] },
      ];
    } else if (damageTypeHint === 'D00') {
      return [
        { type: 'D00', confidence: 0.912, bbox: [0.20, 0.45, 0.82, 0.58] },
      ];
    } else if (damageTypeHint === 'D10') {
      return [
        { type: 'D10', confidence: 0.887, bbox: [0.42, 0.18, 0.58, 0.82] },
      ];
    } else if (damageTypeHint === 'D20') {
      return [
        { type: 'D20', confidence: 0.931, bbox: [0.25, 0.22, 0.78, 0.75] },
      ];
    }
    return [
      { type: 'D40', confidence: 0.892, bbox: [0.32, 0.30, 0.68, 0.70] },
    ];
  }

  return {
    render,
    calculateSeverity,
    generateSyntheticDetections,
    DAMAGE_TYPES,
  };
})();

// Attach globally
window.CivicSightMLViewer = CivicSightMLViewer;
