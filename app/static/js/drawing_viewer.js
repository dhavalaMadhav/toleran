/**
 * Interactive Engineering Drawing Viewer
 * Swiss International Typographic Style & Apple-Level Polish
 * High-DPI pan/zoom viewport, restrained SVG overlays, bidirectional linking,
 * flag cycling, property inspection, and live verification.
 */

let zoomScale = 1.0;
let panX = 0;
let panY = 0;
let isPanning = false;
let startX = 0;
let startY = 0;
let selectedAnnotationId = null;
let currentFlagIndex = -1;

const viewport = document.getElementById('viewport');
const stage = document.getElementById('stage');
const drawingImg = document.getElementById('drawingImage');
const svgOverlay = document.getElementById('annotationSvg');
const zoomLevelText = document.getElementById('zoomLevelText');
const pageSelect = document.getElementById('pageSelect');

function updateTransform() {
  if (stage) {
    stage.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
  }
  if (zoomLevelText) {
    zoomLevelText.textContent = `${Math.round(zoomScale * 100)}%`;
  }
}

function fitToScreen() {
  if (!viewport || !drawingImg) return;
  const vpRect = viewport.getBoundingClientRect();
  const imgW = drawingImg.naturalWidth || drawingImg.width || 800;
  const imgH = drawingImg.naturalHeight || drawingImg.height || 600;

  if (imgW === 0 || imgH === 0) return;

  const scaleX = (vpRect.width - 32) / imgW;
  const scaleY = (vpRect.height - 32) / imgH;
  zoomScale = Math.max(0.15, Math.min(scaleX, scaleY, 1.25));
  panX = Math.round((vpRect.width - imgW * zoomScale) / 2);
  panY = Math.round((vpRect.height - imgH * zoomScale) / 2);
  updateTransform();
}

function zoom(delta, clientX = null, clientY = null) {
  const oldScale = zoomScale;
  let newScale = oldScale + delta;
  newScale = Math.max(0.2, Math.min(newScale, 4.5));

  if (clientX !== null && clientY !== null && viewport) {
    const vpRect = viewport.getBoundingClientRect();
    const mouseX = clientX - vpRect.left;
    const mouseY = clientY - vpRect.top;
    panX = mouseX - ((mouseX - panX) / oldScale) * newScale;
    panY = mouseY - ((mouseY - panY) / oldScale) * newScale;
  } else if (viewport) {
    const vpRect = viewport.getBoundingClientRect();
    panX = vpRect.width / 2 - ((vpRect.width / 2 - panX) / oldScale) * newScale;
    panY = vpRect.height / 2 - ((vpRect.height / 2 - panY) / oldScale) * newScale;
  }

  zoomScale = newScale;
  updateTransform();
}

// Mouse Pan & Zoom Event Listeners
if (viewport) {
  viewport.addEventListener('mousedown', (e) => {
    if (e.button === 0 && !e.target.classList.contains('ann-bbox')) {
      isPanning = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
      viewport.classList.add('panning');
    }
  });

  window.addEventListener('mousemove', (e) => {
    if (!isPanning) return;
    panX = e.clientX - startX;
    panY = e.clientY - startY;
    updateTransform();
  });

  window.addEventListener('mouseup', () => {
    if (isPanning) {
      isPanning = false;
      viewport.classList.remove('panning');
    }
  });

  viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.12 : -0.12;
    zoom(delta, e.clientX, e.clientY);
  }, { passive: false });
}

document.getElementById('zoomInBtn')?.addEventListener('click', () => zoom(0.2));
document.getElementById('zoomOutBtn')?.addEventListener('click', () => zoom(-0.2));
document.getElementById('resetZoomBtn')?.addEventListener('click', () => fitToScreen());

// Render SVG Overlays with Swiss Restraint
function renderOverlays() {
  if (!svgOverlay || !drawingImg) return;
  const w = drawingImg.naturalWidth || drawingImg.width;
  const h = drawingImg.naturalHeight || drawingImg.height;

  if (!w || !h) return;

  svgOverlay.setAttribute('width', w);
  svgOverlay.setAttribute('height', h);
  svgOverlay.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svgOverlay.innerHTML = '';

  const currentPage = pageSelect ? parseInt(pageSelect.value) : 1;
  const annotations = window.ANALYSIS_DATA?.annotations || [];

  const typeFilter = document.getElementById('typeFilter')?.value || 'all';
  const statusFilter = document.getElementById('statusFilter')?.value || 'all';

  annotations.forEach(ann => {
    if (ann.page_number !== currentPage) return;
    if (typeFilter !== 'all' && ann.dimension_type !== typeFilter) return;
    if (statusFilter !== 'all' && ann.verification_status !== statusFilter) return;

    const bbox = ann.bbox;
    if (!bbox) return;

    const rx = bbox.x0 * w;
    const ry = bbox.y0 * h;
    const rw = Math.max(10, (bbox.x1 - bbox.x0) * w);
    const rh = Math.max(10, (bbox.y1 - bbox.y0) * h);

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', rx);
    rect.setAttribute('y', ry);
    rect.setAttribute('width', rw);
    rect.setAttribute('height', rh);

    let statusClass = 'selected';
    if (ann.verification_status === 'auto_accepted' || ann.verification_status === 'approved') {
      statusClass = 'pass';
    } else if (ann.verification_status === 'rejected') {
      statusClass = 'fail';
    } else if (ann.verification_status === 'pending_review' || ann.is_ambiguous) {
      statusClass = 'review';
    }

    rect.setAttribute('class', `ann-bbox ${statusClass}${selectedAnnotationId === ann.id ? ' selected' : ''}`);
    rect.setAttribute('id', `svg-ann-${ann.id}`);
    rect.setAttribute('data-id', ann.id);

    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${ann.original_text} (${ann.dimension_type}) &bull; ${ann.verification_status}`;
    rect.appendChild(title);

    rect.addEventListener('click', (e) => {
      e.stopPropagation();
      selectAnnotation(ann.id, true);
    });

    svgOverlay.appendChild(rect);
  });
}

function selectAnnotation(annId, switchToEditor = false) {
  selectedAnnotationId = annId;
  const ann = (window.ANALYSIS_DATA?.annotations || []).find(a => a.id === annId);
  if (!ann) return;

  // Highlight SVG overlay
  document.querySelectorAll('.ann-bbox').forEach(el => el.classList.remove('selected'));
  const svgEl = document.getElementById(`svg-ann-${annId}`);
  if (svgEl) svgEl.classList.add('selected');

  // Highlight table row and smoothly scroll to it
  document.querySelectorAll('.ann-row').forEach(r => r.classList.remove('selected'));
  const row = document.querySelector(`.ann-row[data-id="${annId}"]`);
  if (row) {
    row.classList.add('selected');
    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Populate Inspector
  populateAnnotationEditor(ann);

  if (switchToEditor) {
    switchTab('editorTab');
  }
}

function populateAnnotationEditor(ann) {
  const container = document.getElementById('selectedAnnotationContainer');
  if (!container) return;

  const isApproved = ann.verification_status === 'approved' || ann.verification_status === 'auto_accepted';
  const isRejected = ann.verification_status === 'rejected';

  container.innerHTML = `
    <div class="selected-annotation-card">
      <div class="card-callout-header">
        <span class="callout-raw-text">${ann.original_text}</span>
        <span class="badge ${isApproved ? 'badge-pass' : (isRejected ? 'badge-fail' : 'badge-review')}">
          ${ann.verification_status}
        </span>
      </div>

      ${ann.crop_image_url ? `
        <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.25rem;">Visual evidence crop</div>
        <img src="${ann.crop_image_url}" class="evidence-crop-preview" alt="Drawing Callout Evidence">
      ` : ''}

      <div class="annotation-property-list">
        <div class="prop-item">
          <span class="prop-name">Dimension type</span>
          <span class="prop-val">${ann.dimension_type}</span>
        </div>
        <div class="prop-item">
          <span class="prop-name">Nominal & unit</span>
          <span class="prop-val">${ann.nominal_value ?? '—'} ${ann.unit}</span>
        </div>
        <div class="prop-item">
          <span class="prop-name">Tolerance type</span>
          <span class="prop-val">${ann.tolerance_type}</span>
        </div>
        <div class="prop-item">
          <span class="prop-name">Permitted interval</span>
          <span class="prop-val text-mono">[${ann.min_val ?? '?'}, ${ann.max_val ?? '?'}]</span>
        </div>
        <div class="prop-item">
          <span class="prop-name">Extraction source</span>
          <span class="prop-val">${ann.extraction_method || 'Vector / OCR'}</span>
        </div>
        <div class="prop-item">
          <span class="prop-name">Confidence</span>
          <span class="prop-val text-mono">${Math.round(ann.confidence * 100)}%</span>
        </div>
      </div>

      ${ann.is_ambiguous ? `
        <div class="ambiguity-banner">
          <div>
            <strong>Flagged for review:</strong> ${ann.ambiguity_reason || 'Manual engineering sign-off required.'}
          </div>
        </div>
      ` : ''}

      <!-- Fast Decision & Correction Form -->
      <form id="correctAnnotationForm" style="border-top: 1px solid var(--border-subtle); padding-top: 1rem; margin-top: 0.5rem;">
        <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.75rem;">
          Verify or adjust dimension
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <div class="form-group">
            <label class="form-label" for="editNominal">Nominal value</label>
            <input type="number" step="0.001" id="editNominal" class="form-control" value="${ann.nominal_value ?? ''}">
          </div>
          <div class="form-group">
            <label class="form-label" for="editType">Type</label>
            <select id="editType" class="form-control">
              <option value="linear" ${ann.dimension_type === 'linear' ? 'selected' : ''}>linear</option>
              <option value="diameter" ${ann.dimension_type === 'diameter' ? 'selected' : ''}>diameter (⌀)</option>
              <option value="radius" ${ann.dimension_type === 'radius' ? 'selected' : ''}>radius (R)</option>
              <option value="thread" ${ann.dimension_type === 'thread' ? 'selected' : ''}>thread</option>
              <option value="angular" ${ann.dimension_type === 'angular' ? 'selected' : ''}>angular</option>
            </select>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <div class="form-group">
            <label class="form-label" for="editUpper">Upper dev (+)</label>
            <input type="number" step="0.001" id="editUpper" class="form-control" value="${ann.upper_deviation ?? 0.0}">
          </div>
          <div class="form-group">
            <label class="form-label" for="editLower">Lower dev (-)</label>
            <input type="number" step="0.001" id="editLower" class="form-control" value="${ann.lower_deviation ?? 0.0}">
          </div>
        </div>

        <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
          <button type="submit" class="btn btn-primary btn-sm" style="flex: 1;">Save correction</button>
          <button type="button" class="btn btn-success btn-sm" onclick="approveAnnotationQuick(${ann.id})">Approve</button>
          <button type="button" class="btn btn-danger btn-sm" onclick="rejectCurrentAnnotation(${ann.id})">Reject</button>
        </div>
      </form>
    </div>
  `;

  document.getElementById('correctAnnotationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      nominal_value: parseFloat(document.getElementById('editNominal').value),
      dimension_type: document.getElementById('editType').value,
      upper_deviation: parseFloat(document.getElementById('editUpper').value),
      lower_deviation: parseFloat(document.getElementById('editLower').value),
      verification_status: 'corrected',
      notes: 'Corrected by engineer in Drawing Viewer'
    };

    try {
      const res = await fetch(`/api/v1/annotations/${ann.id}/correct`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        showToast('Dimension updated & verified', 'success');
        setTimeout(() => location.reload(), 350);
      } else {
        showToast('Error updating dimension', 'error');
      }
    } catch (err) {
      showToast('Error: ' + err.message, 'error');
    }
  });
}

async function approveAnnotationQuick(annId) {
  try {
    const res = await fetch(`/api/v1/review/annotation/${annId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'approved', notes: 'Verified in drawing viewer' })
    });
    if (res.ok) {
      showToast('Annotation approved', 'success');
      setTimeout(() => location.reload(), 350);
    } else {
      showToast('Failed to approve', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function rejectCurrentAnnotation(annId) {
  if (!confirm('Reject this extracted annotation?')) return;
  try {
    const res = await fetch(`/api/v1/annotations/${annId}/reject`, { method: 'POST' });
    if (res.ok) {
      showToast('Annotation rejected', 'info');
      setTimeout(() => location.reload(), 350);
    }
  } catch (err) {
    showToast('Failed to reject: ' + err.message, 'error');
  }
}

function zoomToAnnotation(ann) {
  if (!viewport || !drawingImg || !ann.bbox) return;
  const w = drawingImg.naturalWidth || drawingImg.width;
  const h = drawingImg.naturalHeight || drawingImg.height;
  const cx = ((ann.bbox.x0 + ann.bbox.x1) / 2) * w;
  const cy = ((ann.bbox.y0 + ann.bbox.y1) / 2) * h;

  zoomScale = 1.75;
  const vpRect = viewport.getBoundingClientRect();
  panX = Math.round(vpRect.width / 2 - cx * zoomScale);
  panY = Math.round(vpRect.height / 2 - cy * zoomScale);
  updateTransform();
}

// Table row clicks
document.querySelectorAll('.ann-row').forEach(row => {
  row.addEventListener('click', () => {
    const id = parseInt(row.dataset.id);
    const ann = (window.ANALYSIS_DATA?.annotations || []).find(a => a.id === id);
    if (ann) {
      selectAnnotation(id, false);
      zoomToAnnotation(ann);
    }
  });
});

// Tab switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');

  const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick')?.includes(tabId));
  if (activeBtn) activeBtn.classList.add('active');

  const pane = document.getElementById(tabId);
  if (pane) pane.style.display = 'block';
}

// Page selector change
pageSelect?.addEventListener('change', () => {
  const opt = pageSelect.selectedOptions[0];
  if (opt && drawingImg) {
    drawingImg.src = opt.dataset.img;
    drawingImg.onload = () => {
      renderOverlays();
      fitToScreen();
    };
  }
});

// Toggle overlays
document.getElementById('toggleOverlaysBtn')?.addEventListener('click', (e) => {
  if (svgOverlay) {
    const isHidden = svgOverlay.style.display === 'none';
    svgOverlay.style.display = isHidden ? 'block' : 'none';
    const btn = document.getElementById('toggleOverlaysBtn');
    if (btn) btn.classList.toggle('active', isHidden);
  }
});

// Flagged Characteristic Cycling
function getFlaggedAnnotations() {
  const annotations = window.ANALYSIS_DATA?.annotations || [];
  return annotations.filter(a => a.verification_status === 'pending_review' || a.is_ambiguous);
}

document.getElementById('nextFlagBtn')?.addEventListener('click', () => {
  const flagged = getFlaggedAnnotations();
  if (flagged.length === 0) {
    showToast('No flagged characteristics found', 'info');
    return;
  }
  currentFlagIndex = (currentFlagIndex + 1) % flagged.length;
  const ann = flagged[currentFlagIndex];
  selectAnnotation(ann.id, true);
  zoomToAnnotation(ann);
});

document.getElementById('prevFlagBtn')?.addEventListener('click', () => {
  const flagged = getFlaggedAnnotations();
  if (flagged.length === 0) {
    showToast('No flagged characteristics found', 'info');
    return;
  }
  currentFlagIndex = (currentFlagIndex - 1 + flagged.length) % flagged.length;
  const ann = flagged[currentFlagIndex];
  selectAnnotation(ann.id, true);
  zoomToAnnotation(ann);
});

// Filters
document.getElementById('typeFilter')?.addEventListener('change', () => {
  filterTableRows();
  renderOverlays();
});

document.getElementById('statusFilter')?.addEventListener('change', () => {
  filterTableRows();
  renderOverlays();
});

function filterTableRows() {
  const typeFilter = document.getElementById('typeFilter')?.value || 'all';
  const statusFilter = document.getElementById('statusFilter')?.value || 'all';

  document.querySelectorAll('.ann-row').forEach(row => {
    const typeMatch = typeFilter === 'all' || row.dataset.type === typeFilter;
    const statusMatch = statusFilter === 'all' || row.dataset.status === statusFilter;
    row.style.display = (typeMatch && statusMatch) ? '' : 'none';
  });
}

// Initial startup
window.addEventListener('load', () => {
  if (drawingImg) {
    if (drawingImg.complete) {
      renderOverlays();
      fitToScreen();
    } else {
      drawingImg.onload = () => {
        renderOverlays();
        fitToScreen();
      };
    }
  }
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
});
