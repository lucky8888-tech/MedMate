// SafeDose Scan Module - Camera/Scan Medicine feature.
// Self-contained: reads the shared allergies + do-not-substitute controls from
// the DOM and renders into the shared results section. It reuses app.js's
// result renderer (window.SafeDose.renderResults) for a consistent view, so it
// does not duplicate result-card markup and does not alter app.js behaviour.

document.addEventListener('DOMContentLoaded', () => {
  const scanDropzone = document.getElementById('scanDropzone');
  const scanImageInput = document.getElementById('scanImageInput');
  const scanDropzoneContent = document.getElementById('scanDropzoneContent');
  const scanPreview = document.getElementById('scanPreview');
  const scanRetakeBtn = document.getElementById('scanRetakeBtn');
  const scanIdentifyBtn = document.getElementById('scanIdentifyBtn');
  const scanStatusNote = document.getElementById('scanStatusNote');

  // Shared result nodes (same elements app.js uses)
  const loadingIndicator = document.getElementById('loadingIndicator');
  const resultsSection = document.getElementById('resultsSection');
  const scanSummary = document.getElementById('scanSummary');
  const prescribedCard = document.getElementById('prescribedCard');
  const alternativesContainer = document.getElementById('alternativesContainer');
  const alternativesCountBadge = document.getElementById('alternativesCountBadge');
  const excludedSection = document.getElementById('excludedSection');
  const excludedList = document.getElementById('excludedList');
  const excludedCount = document.getElementById('excludedCount');

  let selectedFile = null;

  // --- Check OCR availability on load so the UI can warn early ---
  fetch('/api/scan/status').then(r => r.json()).then(data => {
    if (!data.ocr_available || !data.binary_ready) {
      if (scanStatusNote) {
        scanStatusNote.innerHTML =
          '<strong>OCR is not available on this server.</strong> Install the Tesseract OCR ' +
          'engine and the pytesseract/Pillow packages to enable scanning. The text search ' +
          'still works fully.';
        scanStatusNote.style.display = 'block';
      }
    }
  }).catch(() => {});

  // --- Helpers: read the shared controls that live in the search card ---
  function getSelectedAllergies() {
    const tags = document.querySelectorAll('#selectedAllergiesList .active-allergy-tag > span');
    return Array.from(tags).map(s => s.textContent.trim()).filter(Boolean);
  }

  function getDoNotSubstitute() {
    const t = document.getElementById('doNotSubstituteToggle');
    return t ? t.checked : false;
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // --- File selection / preview ---
  scanDropzone.addEventListener('click', () => scanImageInput.click());

  scanImageInput.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) handleFile(file);
  });

  // Drag & drop for desktop uploads
  ['dragenter', 'dragover'].forEach(evt => {
    scanDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      scanDropzone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach(evt => {
    scanDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      scanDropzone.classList.remove('dragover');
    });
  });
  scanDropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) handleFile(file);
  });

  function handleFile(file) {
    selectedFile = file;
    scanPreview.src = URL.createObjectURL(file);
    scanPreview.style.display = 'block';
    scanDropzoneContent.style.display = 'none';
    scanRetakeBtn.style.display = 'inline-flex';
    scanIdentifyBtn.disabled = false;
  }

  scanRetakeBtn.addEventListener('click', resetScanInput);

  function resetScanInput() {
    selectedFile = null;
    scanImageInput.value = '';
    scanPreview.style.display = 'none';
    scanPreview.src = '';
    scanDropzoneContent.style.display = 'flex';
    scanRetakeBtn.style.display = 'none';
    scanIdentifyBtn.disabled = true;
  }

  // --- Scan action ---
  scanIdentifyBtn.addEventListener('click', runScan);

  async function runScan() {
    if (!selectedFile) return;

    loadingIndicator.style.display = 'flex';
    resultsSection.style.display = 'none';
    scanSummary.style.display = 'none';

    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('allergies', JSON.stringify(getSelectedAllergies()));
    formData.append('do_not_substitute', getDoNotSubstitute() ? 'true' : 'false');

    try {
      const resp = await fetch('/api/scan', { method: 'POST', body: formData });
      const data = await resp.json();
      loadingIndicator.style.display = 'none';

      if (!resp.ok) {
        renderScanError(data.error || 'Scanning failed. Please try again.');
        return;
      }
      renderScanResults(data);
    } catch (err) {
      loadingIndicator.style.display = 'none';
      renderScanError('Network error connecting to SafeDose server. Please try again.');
    }
  }

  function renderScanError(msg) {
    resultsSection.style.display = 'flex';
    scanSummary.style.display = 'block';
    scanSummary.className = 'card scan-summary-card';
    scanSummary.innerHTML =
      '<div class="scan-banner scan-banner-error">' +
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">' +
      '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' +
      '<div>' + escapeHtml(msg) + '</div></div>';
    prescribedCard.innerHTML = '';
    alternativesContainer.innerHTML = '';
    alternativesCountBadge.textContent = '0 Found';
    excludedSection.style.display = 'none';
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  }

  function renderScanResults(data) {
    const matches = data.matches || [];
    const ocrConf = data.ocr_confidence || 0;
    const uncertain = !!data.uncertain;
    const warning = data.warning || null;
    const extracted = (data.extracted_text || '').trim();

    // --- Scan summary banner (OCR confidence, uncertainty, extracted text) ---
    let html = '';

    const confLabel = ocrConf >= 70 ? 'Good' : ocrConf >= 40 ? 'Low' : 'Very low';
    const confClass = ocrConf >= 70 ? 'conf-good' : ocrConf >= 40 ? 'conf-low' : 'conf-vlow';
    html += '<div class="scan-meta">' +
      '<span class="scan-conf ' + confClass + '">OCR confidence: ' + ocrConf + '% (' + confLabel + ')</span>' +
      '<span class="scan-text-basis">Identified from printed label text &mdash; not colour or appearance</span>' +
      '</div>';

    if (uncertain && warning) {
      html += '<div class="scan-banner scan-banner-warn">' +
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">' +
        '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>' +
        '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' +
        '<div><strong>Identification unclear.</strong> ' + escapeHtml(warning) + '</div></div>';
    } else if (warning) {
      html += '<div class="scan-banner scan-banner-info">' +
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">' +
        '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>' +
        '<div>' + escapeHtml(warning) + '</div></div>';
    }

    if (extracted) {
      html += '<div class="scan-extracted"><strong>Text read from label:</strong>' +
        '<span class="scan-extracted-text">' + escapeHtml(extracted) + '</span></div>';
    }

    if (matches.length > 0) {
      html += '<div class="scan-candidates"><strong>Possible matches found in text:</strong><ul>' +
        matches.map(m =>
          '<li><span class="cand-brand">' + escapeHtml(m.brand) +
          ' <span class="cand-id">(' + escapeHtml(m.id) + ')</span></span>' +
          '<span class="cand-meta">' + escapeHtml(m.active_ingredients) + ' &bull; ' +
          escapeHtml(m.strength) + ' &bull; ' + escapeHtml(m.form) + '</span>' +
          '<span class="cand-signals">' + m.signals.map(escapeHtml).join(', ') + '</span></li>'
        ).join('') + '</ul></div>';
    }

    html += '<p class="scan-disclaimer">SafeDose reads printed label text only and never identifies ' +
      'medicines by colour or appearance. It does not recommend dosage from a photo. Always confirm with a pharmacist.</p>';

    scanSummary.className = 'card scan-summary-card' + (uncertain ? ' scan-summary-uncertain' : '');
    scanSummary.innerHTML = html;
    scanSummary.style.display = 'block';

    // --- Detailed results: reuse app.js renderer when the engine matched ---
    const suggestResult = data.suggest_result;
    if (suggestResult && !suggestResult.error && window.SafeDose && window.SafeDose.renderResults) {
      // Reuse the exact same result view as the text search (prescribed card +
      // allergy-checked alternatives + excluded candidates).
      window.SafeDose.renderResults(suggestResult);
    } else if (matches.length === 0) {
      prescribedCard.innerHTML = '';
      alternativesContainer.innerHTML =
        '<div class="card" style="text-align:center;padding:24px;color:var(--text-muted);">' +
        '<p>No medicine could be identified from the captured photo. ' + escapeHtml(warning || '') + '</p></div>';
      alternativesCountBadge.textContent = '0 Found';
      excludedSection.style.display = 'none';
      resultsSection.style.display = 'flex';
      resultsSection.scrollIntoView({ behavior: 'smooth' });
      return;
    } else {
      // Fallback: show the best text match minimally if the engine did not enrich.
      const m = matches[0];
      prescribedCard.innerHTML =
        '<div class="prescribed-header"><div>' +
        '<span style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;color:#10B981;font-weight:700;">Best Text Match</span>' +
        '<h3 class="prescribed-brand">' + escapeHtml(m.brand) +
        ' <span style="font-size:0.9rem;color:var(--text-dim);font-weight:normal;">(' + escapeHtml(m.id) + ')</span></h3>' +
        '</div></div>' +
        '<div class="prescribed-meta"><strong>Active Ingredients:</strong> ' + escapeHtml(m.active_ingredients) +
        ' &bull; ' + escapeHtml(m.strength) + ' &bull; ' + escapeHtml(m.form) + '</div>' +
        (m.used_for ? '<div class="indication-pill"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> Used For: ' + escapeHtml(m.used_for) + '</div>' : '');
      alternativesContainer.innerHTML = '';
      alternativesCountBadge.textContent = '0 Found';
      excludedSection.style.display = 'none';
    }

    resultsSection.style.display = 'flex';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});
