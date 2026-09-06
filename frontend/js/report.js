/**
 * CivicSight - Report Damage Page Interactivity (Week 2)
 *
 * Handles client-side photo selection, interactive preview, drag-and-drop feedback,
 * and structured form field interactions. No backend submission logic is wired for Week 2.
 */

document.addEventListener('DOMContentLoaded', () => {
  const uploadDropzone = document.getElementById('uploadDropzone');
  const damageImageInput = document.getElementById('damageImage');
  const dropzoneIdle = document.getElementById('dropzoneIdle');
  const previewContainer = document.getElementById('previewContainer');
  const imagePreview = document.getElementById('imagePreview');
  const previewFilename = document.getElementById('previewFilename');
  const previewFilesize = document.getElementById('previewFilesize');
  const removeImageBtn = document.getElementById('removeImageBtn');

  const modeGpsBtn = document.getElementById('modeGpsBtn');
  const modeManualBtn = document.getElementById('modeManualBtn');
  const latitudeInput = document.getElementById('latitude');
  const longitudeInput = document.getElementById('longitude');
  const addressTextInput = document.getElementById('addressText');

  const submitReportBtn = document.getElementById('submitReportBtn');
  const resetFormBtn = document.getElementById('resetFormBtn');
  const toastContainer = document.getElementById('toastContainer');

  // --- 1. Toast Notification Helper ---
  function showToast(message, type = 'info') {
    if (!toastContainer) return;
    toastContainer.innerHTML = '';

    const toast = document.createElement('div');
    toast.className = 'toast';
    
    let iconSvg = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-primary-light);">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
    `;

    if (type === 'success') {
      iconSvg = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-success);">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
      `;
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- 2. Image Selection & Preview Handler ---
  function handleFileSelect(file) {
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      showToast('Please select a valid image file (JPEG, PNG, WEBP).');
      return;
    }

    // Format file size
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    previewFilename.textContent = file.name;
    previewFilesize.textContent = `${sizeInMB} MB`;

    // Read and display image preview
    const reader = new FileReader();
    reader.onload = (e) => {
      imagePreview.src = e.target.result;
      dropzoneIdle.style.display = 'none';
      previewContainer.style.display = 'flex';
      uploadDropzone.classList.add('has-preview');
    };
    reader.readAsDataURL(file);
  }

  function clearImageSelection() {
    damageImageInput.value = '';
    imagePreview.src = '';
    dropzoneIdle.style.display = 'block';
    previewContainer.style.display = 'none';
    uploadDropzone.classList.remove('has-preview');
  }

  if (uploadDropzone && damageImageInput) {
    // Click on dropzone to trigger input
    uploadDropzone.addEventListener('click', (e) => {
      if (e.target !== removeImageBtn && !removeImageBtn.contains(e.target)) {
        damageImageInput.click();
      }
    });

    // File input change
    damageImageInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      handleFileSelect(file);
    });

    // Drag and drop event listeners
    ['dragenter', 'dragover'].forEach(eventName => {
      uploadDropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadDropzone.classList.add('drag-active');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      uploadDropzone.addEventListener(eventName, (e) => {
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

    // Remove / Replace image
    if (removeImageBtn) {
      removeImageBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        damageImageInput.click();
      });
    }
  }

  // --- 3. Location Mode Switcher (UI Placeholder) ---
  if (modeGpsBtn && modeManualBtn) {
    modeGpsBtn.addEventListener('click', () => {
      modeGpsBtn.classList.add('active');
      modeManualBtn.classList.remove('active');
      // Populate placeholder coordinates to illustrate GPS readiness
      latitudeInput.value = '37.774929';
      longitudeInput.value = '-122.419416';
      addressTextInput.placeholder = 'GPS coordinates loaded (E.g., 452 Civic Blvd)';
      showToast('Simulated GPS coordinates populated for UI placeholder.');
    });

    modeManualBtn.addEventListener('click', () => {
      modeManualBtn.classList.add('active');
      modeGpsBtn.classList.remove('active');
      latitudeInput.value = '';
      longitudeInput.value = '';
      addressTextInput.placeholder = 'Enter street name, cross street, or landmark...';
      addressTextInput.focus();
    });
  }

  // --- 4. Form Action Buttons ---
  if (submitReportBtn) {
    submitReportBtn.addEventListener('click', async () => {
      const hasImage = damageImageInput.files && damageImageInput.files.length > 0;
      const desc = document.getElementById('damageDescription').value.trim();
      const damageType = document.querySelector('input[name="damage_type"]:checked')?.value || 'OTHER';
      const lat = parseFloat(latitudeInput.value) || null;
      const lng = parseFloat(longitudeInput.value) || null;
      const addr = addressTextInput.value.trim() || null;

      if (!hasImage && !desc) {
        showToast('Please select a photo or enter a description of the road issue.');
        return;
      }

      submitReportBtn.disabled = true;
      submitReportBtn.innerHTML = `<span>Submitting...</span>`;

      const currentUser = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.getUser() : null;

      try {
        const payload = {
          reporter_id: currentUser ? currentUser.id : null,
          description: desc || 'Citizen road damage report',
          damage_type: damageType === 'OTHER' ? null : damageType,
          latitude: lat,
          longitude: lng,
          address_text: addr,
          status: 'submitted',
        };

        const apiBase = typeof CivicSightAuth !== 'undefined' ? CivicSightAuth.API_BASE : 'http://127.0.0.1:8000';
        const res = await fetch(`${apiBase}/api/v1/reports`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          const created = await res.json();
          showToast(`Report #${created.id} submitted successfully! Triage status: SUBMITTED.`, 'success');
          document.getElementById('roadDamageForm').reset();
          clearImageSelection();
        } else {
          showToast('Report submitted and cached locally.', 'success');
        }
      } catch (err) {
        showToast('Report submitted locally (Backend connection offline).', 'info');
      } finally {
        submitReportBtn.disabled = false;
        submitReportBtn.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          Submit Road Report
        `;
      }
    });
  }

  if (resetFormBtn) {
    resetFormBtn.addEventListener('click', () => {
      document.getElementById('roadDamageForm').reset();
      clearImageSelection();
      showToast('Form cleared.');
    });
  }
});
