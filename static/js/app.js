// SafeDose Client Application Logic

document.addEventListener('DOMContentLoaded', () => {
  // PWA Service Worker Registration
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js').catch(err => {
      console.log('SW registration error:', err);
    });
  }

  // PWA Install Prompt Handler
  let deferredPrompt;
  const installAppBtn = document.getElementById('installAppBtn');
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installAppBtn.style.display = 'inline-flex';
  });

  installAppBtn.addEventListener('click', async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') {
        installAppBtn.style.display = 'none';
      }
      deferredPrompt = null;
    }
  });

  // DOM Elements
  const searchInput = document.getElementById('medicineSearchInput');
  const clearSearchBtn = document.getElementById('clearSearchBtn');
  const autocompleteList = document.getElementById('autocompleteList');
  const customAllergyInput = document.getElementById('customAllergyInput');
  const addAllergyBtn = document.getElementById('addAllergyBtn');
  const selectedAllergiesList = document.getElementById('selectedAllergiesList');
  const doNotSubstituteToggle = document.getElementById('doNotSubstituteToggle');
  const checkAlternativesBtn = document.getElementById('checkAlternativesBtn');
  const loadingIndicator = document.getElementById('loadingIndicator');
  const resultsSection = document.getElementById('resultsSection');
  const prescribedCard = document.getElementById('prescribedCard');
  const alternativesContainer = document.getElementById('alternativesContainer');
  const alternativesCountBadge = document.getElementById('alternativesCountBadge');
  const excludedSection = document.getElementById('excludedSection');
  const excludedList = document.getElementById('excludedList');
  const excludedCount = document.getElementById('excludedCount');
  const excludedAccordionToggle = document.getElementById('excludedAccordionToggle');
  const excludedAccordionBody = document.getElementById('excludedAccordionBody');

  // State
  let localMedicines = [];
  let selectedAllergies = new Set();

  // Load medicines list for instant client-side autocomplete
  fetch('/api/medicines')
    .then(r => r.json())
    .then(data => {
      localMedicines = data.medicines || [];
    })
    .catch(() => {});

  // Search input events
  searchInput.addEventListener('input', () => {
    const val = searchInput.value.trim().toLowerCase();
    clearSearchBtn.style.display = val ? 'block' : 'none';

    if (!val || val.length < 1) {
      autocompleteList.style.display = 'none';
      return;
    }

    const matches = localMedicines.filter(m => 
      m.brand.toLowerCase().includes(val) || 
      m.active_ingredients.toLowerCase().includes(val) ||
      m.id.toLowerCase().includes(val)
    ).slice(0, 6);

    if (matches.length > 0) {
      autocompleteList.innerHTML = matches.map(m => `
        <div class="autocomplete-item" data-brand="${m.brand}">
          <div class="item-brand">${m.brand} <span style="font-weight: normal; color: #94A3B8;">(${m.id})</span></div>
          <div class="item-meta">${m.active_ingredients} • ${m.strength} • ${m.used_for || ''}</div>
        </div>
      `).join('');
      autocompleteList.style.display = 'block';
    } else {
      autocompleteList.style.display = 'none';
    }
  });

  clearSearchBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
    autocompleteList.style.display = 'none';
    searchInput.focus();
  });

  autocompleteList.addEventListener('click', (e) => {
    const item = e.target.closest('.autocomplete-item');
    if (item) {
      searchInput.value = item.getAttribute('data-brand');
      autocompleteList.style.display = 'none';
      clearSearchBtn.style.display = 'block';
      runSearch();
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-input-wrapper') && !e.target.closest('.autocomplete-list')) {
      autocompleteList.style.display = 'none';
    }
  });

  // Popular quick chips
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      searchInput.value = chip.getAttribute('data-med');
      clearSearchBtn.style.display = 'block';
      runSearch();
    });
  });

  // Common allergy toggle chips
  document.querySelectorAll('.allergy-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const allergy = chip.getAttribute('data-allergy');
      if (selectedAllergies.has(allergy)) {
        selectedAllergies.delete(allergy);
        chip.classList.remove('selected');
      } else {
        selectedAllergies.add(allergy);
        chip.classList.add('selected');
      }
      renderActiveAllergyTags();
    });
  });

  // Custom allergy addition
  function addCustomAllergy() {
    const val = customAllergyInput.value.trim();
    if (!val) return;
    selectedAllergies.add(val);
    customAllergyInput.value = '';
    renderActiveAllergyTags();
  }

  addAllergyBtn.addEventListener('click', addCustomAllergy);
  customAllergyInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addCustomAllergy();
    }
  });

  function renderActiveAllergyTags() {
    selectedAllergiesList.innerHTML = Array.from(selectedAllergies).map(a => `
      <span class="active-allergy-tag">
        <span>${a}</span>
        <button type="button" class="remove-tag-btn" data-allergy="${a}" aria-label="Remove ${a}">&times;</button>
      </span>
    `).join('');

    // Re-sync common chips selection visual state
    document.querySelectorAll('.allergy-chip').forEach(chip => {
      const a = chip.getAttribute('data-allergy');
      if (selectedAllergies.has(a)) {
        chip.classList.add('selected');
      } else {
        chip.classList.remove('selected');
      }
    });
  }

  selectedAllergiesList.addEventListener('click', (e) => {
    const btn = e.target.closest('.remove-tag-btn');
    if (btn) {
      const a = btn.getAttribute('data-allergy');
      selectedAllergies.delete(a);
      renderActiveAllergyTags();
    }
  });

  // Accordion for excluded products
  excludedAccordionToggle.addEventListener('click', () => {
    const isVisible = excludedAccordionBody.style.display === 'block';
    excludedAccordionBody.style.display = isVisible ? 'none' : 'block';
    const arrow = excludedAccordionToggle.querySelector('.accordion-arrow');
    if (arrow) arrow.classList.toggle('rotated', !isVisible);
  });

  // Search Action
  checkAlternativesBtn.addEventListener('click', runSearch);

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      autocompleteList.style.display = 'none';
      runSearch();
    }
  });

  async function runSearch() {
    const query = searchInput.value.trim();
    if (!query) {
      searchInput.focus();
      return;
    }

    loadingIndicator.style.display = 'flex';
    resultsSection.style.display = 'none';
    const scanSummaryEl = document.getElementById('scanSummary');
    if (scanSummaryEl) scanSummaryEl.style.display = 'none';

    try {
      const response = await fetch('/api/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          allergies: Array.from(selectedAllergies),
          do_not_substitute: doNotSubstituteToggle.checked
        })
      });

      const data = await response.json();
      loadingIndicator.style.display = 'none';

      if (!response.ok) {
        showError(data.error || 'Failed to find medicine.');
        return;
      }

      renderResults(data);
    } catch (err) {
      loadingIndicator.style.display = 'none';
      showError('Network error connecting to SafeDose server. Please try again.');
    }
  }

  function showError(msg) {
    resultsSection.style.display = 'block';
    prescribedCard.innerHTML = `
      <div class="warning-banner" style="background: rgba(244, 63, 94, 0.15); border-color: rgba(244, 63, 94, 0.4); color: #FECDD3;">
        <strong>[!] Notice:</strong> ${msg}
      </div>
    `;
    alternativesContainer.innerHTML = '';
    alternativesCountBadge.textContent = '0 Found';
    excludedSection.style.display = 'none';
  }

  function renderResults(data) {
    const pres = data.prescribed;
    const alts = data.alternatives || [];
    const excluded = data.excluded || [];

    // 1. Render Prescribed Card
    let flagsHtml = '';
    if (pres.flags && pres.flags.length > 0) {
      flagsHtml = pres.flags.map(f => `
        <div class="alert-banner">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <div>${f}</div>
        </div>
      `).join('');
    } else {
      flagsHtml = `
        <div style="font-size: 0.8rem; color: #6EE7B7; display: flex; align-items: center; gap: 6px; margin-top: 8px;">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          No listed allergy triggers found for prescribed medicine.
        </div>
      `;
    }

    let indicationHtml = '';
    if (pres.indications) {
      indicationHtml = `
        <div class="indication-pill">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          Used For: ${pres.indications}
        </div>
      `;
    }

    prescribedCard.innerHTML = `
      <div class="prescribed-header">
        <div>
          <span style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.5px; color: #10B981; font-weight: 700;">Prescribed Product</span>
          <h3 class="prescribed-brand">${pres.brand} <span style="font-size: 0.9rem; color: var(--text-dim); font-weight: normal;">(${pres.id})</span></h3>
        </div>
        <span class="source-tag">${pres.source || 'Local Database'}</span>
      </div>
      <div class="prescribed-meta">
        <strong>Active Ingredients:</strong> ${pres.active_ingredients || 'N/A'}
      </div>
      ${indicationHtml}
      ${flagsHtml}
    `;

    // 2. Do Not Substitute Notice
    if (data.message && doNotSubstituteToggle.checked) {
      alternativesContainer.innerHTML = `
        <div class="warning-banner" style="margin-top: 10px;">
          <strong>[!] Notice:</strong> ${data.message}
        </div>
      `;
      alternativesCountBadge.textContent = 'Blocked';
      alternativesCountBadge.className = 'badge';
      alternativesCountBadge.style.background = 'rgba(245, 158, 11, 0.2)';
      alternativesCountBadge.style.color = '#FDE68A';
      excludedSection.style.display = 'none';
      resultsSection.style.display = 'flex';
      resultsSection.scrollIntoView({ behavior: 'smooth' });
      return;
    }

    // 3. Render Alternatives
    alternativesCountBadge.textContent = `${alts.length} Found`;
    alternativesCountBadge.className = 'badge badge-success';

    if (alts.length === 0) {
      alternativesContainer.innerHTML = `
        <div class="card" style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 0.88rem;">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 8px; color: var(--text-dim);"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          <p>${data.message || 'No safe alternatives could be confirmed from the data provided. Ask your pharmacist.'}</p>
        </div>
      `;
    } else {
      alternativesContainer.innerHTML = alts.map(alt => {
        let savingsHtml = '';
        if (alt.savings && alt.savings.saves_money) {
          savingsHtml = `
            <span class="savings-tag">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              Saves ${alt.savings.savings_amount} (${alt.savings.savings_percent})
            </span>
          `;
        }

        return `
          <div class="alt-card">
            <div class="alt-header">
              <div>
                <h4 class="alt-brand">${alt.brand} <span style="font-size: 0.85rem; font-weight: normal; color: var(--text-dim);">(${alt.id})</span></h4>
                <span class="alt-manufacturer">by ${alt.manufacturer} • ${alt.pack_size}</span>
              </div>
              <div class="alt-price">${alt.price_per_pack}</div>
            </div>

            ${savingsHtml}

            <div class="alt-inactives">
              <strong>Inactive Ingredients:</strong> ${alt.inactive_ingredients || 'None listed'}
            </div>

            <div class="safety-check-note">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
              ${alt.safety_note}
            </div>
          </div>
        `;
      }).join('');
    }

    // 4. Excluded Candidates
    if (excluded.length > 0) {
      excludedCount.textContent = excluded.length;
      excludedList.innerHTML = excluded.map(exc => `
        <li>
          <strong>${exc.id}:</strong> ${exc.reason}
        </li>
      `).join('');
      excludedSection.style.display = 'block';
    } else {
      excludedSection.style.display = 'none';
    }

    resultsSection.style.display = 'flex';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Expose renderers so the scan module (scan.js) can reuse them without
  // duplicating the result-card markup.
  window.SafeDose = window.SafeDose || {};
  window.SafeDose.renderResults = renderResults;
  window.SafeDose.showError = showError;
});
