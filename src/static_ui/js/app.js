let currentUser = null;
let availableTemplates = [];
let pendingReplacementUpload = null;
let selectedStreamingFile = null;

async function init() {
  requireAuth();
  await loadUser();
  await loadTemplates();
  await loadHistory();
}

function showSection(section) {
  if (section === 'configurations' && currentUser?.role !== 'admin') section = 'weekly';
  const weekly = section === 'weekly';
  const streaming = section === 'streaming';
  const configurations = section === 'configurations';
  document.getElementById('weekly-section').classList.toggle('hidden', !weekly);
  document.getElementById('streaming-section').classList.toggle('hidden', !streaming);
  document.getElementById('configurations-section').classList.toggle('hidden', !configurations);
  document.getElementById('weekly-nav').className = navClass(weekly);
  document.getElementById('streaming-nav').className = navClass(streaming);
  const configurationsNav = document.getElementById('configurations-nav');
  configurationsNav.className = `${configurationsNav.classList.contains('hidden') ? 'hidden ' : ''}${navClass(configurations)}`;
  document.getElementById('mobile-section-select').value = section;
  if (streaming) loadStreamingHistory();
  if (configurations) loadConfigurationRuns();
}

function navClass(active) {
  return `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left ${active ? 'bg-blue-50 text-brand' : 'text-gray-500 hover:bg-gray-50'}`;
}

async function loadUser() {
  const res = await fetch(`${API}/auth/me`, { headers: authHeaders() });
  if (res.status === 401) { logout(); return; }
  currentUser = await res.json();
  const displayName = [currentUser.first_name, currentUser.last_name].filter(Boolean).join(' ')
    || currentUser.username
    || currentUser.email
    || 'User';
  document.getElementById('user-name').textContent = displayName;
  document.getElementById('user-team').textContent = currentUser.role || '';
  document.getElementById('user-avatar').textContent = displayName.charAt(0).toUpperCase();
  if (currentUser.role === 'admin') {
    document.getElementById('configurations-nav').classList.remove('hidden');
    document.getElementById('configurations-mobile-option').classList.remove('hidden');
  }
}

async function loadTemplates() {
  const res = await fetch(`${API}/clean/available-templates`, { headers: authHeaders() });
  const data = await res.json();
  availableTemplates = data.templates;

  // Populate download list
  const downloadList = document.getElementById('template-list');
  if (!availableTemplates.length) {
    downloadList.innerHTML = `
      <p class="text-sm text-gray-400 py-4 text-center">
        No templates available for your account.
      </p>`;

    document.getElementById('template-select').innerHTML =
      `<option value="">No templates available</option>`;
    return;
  }

  downloadList.innerHTML = availableTemplates.map(t => `
    <div class="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
          <svg class="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2
                 h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        </div>
        <span class="text-sm font-medium text-gray-800">${t.display_name}</span>
      </div>
      <a href="#"
         onclick="addAuthToDownload(event, '${t.filename}')"
         class="text-xs font-medium text-brand hover:text-blue-700 flex items-center gap-1">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
        </svg>
        Download
      </a>
    </div>
  `).join('');

  // Populate upload dropdown
  const select = document.getElementById('template-select');
  select.innerHTML = `<option value="">— Select a template —</option>` +
    availableTemplates.map(t =>
      `<option value="${t.filename}">${t.display_name}</option>`
    ).join('');
}

async function addAuthToDownload(e, filename) {
  e.preventDefault();
  const res = await fetch(`${API}/templates/download/${filename}`, {
    headers: authHeaders()
  });
  if (!res.ok) { alert('Download failed.'); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function loadHistory() {
  const res = await fetch(`${API}/clean/history`, { headers: authHeaders() });
  const logs = await res.json();
  const tbody = document.getElementById('history-body');

  if (!logs.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="px-4 py-8 text-center text-sm text-gray-400">
          No uploads yet.
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = logs.map(l => `
    <tr class="hover:bg-gray-50 transition">
      <td class="px-4 py-3 text-sm text-gray-700">${l.original_filename}</td>
      <td class="px-4 py-3 text-sm text-gray-500">${l.template_name}</td>
      <td class="px-4 py-3 text-sm text-gray-500">${l.rows_input}</td>
      <td class="px-4 py-3 text-sm text-gray-500">${l.rows_output}</td>
      <td class="px-4 py-3 text-sm text-gray-500">${l.issues_fixed}</td>
      <td class="px-4 py-3">
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
          ${l.status === 'success'
      ? 'bg-green-100 text-green-700'
      : 'bg-red-100 text-red-700'}">
          ${l.status}
        </span>
      </td>
    </tr>
  `).join('');
}

// ── Upload flow ───────────────────────────────────────────────────────────────

let dropzone = null;
let fileInput = null;
let selectedFile = null;

function setupDropzone() {
  dropzone = document.getElementById('dropzone');
  fileInput = document.getElementById('file-input');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('dragover', e => {
    e.preventDefault();
    dropzone.classList.add('border-brand', 'bg-blue-50');
  });
  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('border-brand', 'bg-blue-50');
  });
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('border-brand', 'bg-blue-50');
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
  });
  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setSelectedFile(fileInput.files[0]);
  });
}

function setupStreamingDropzone() {
  const zone = document.getElementById('streaming-dropzone');
  const input = document.getElementById('streaming-file-input');
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    zone.classList.add('border-brand', 'bg-blue-50');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('border-brand', 'bg-blue-50'));
  zone.addEventListener('drop', event => {
    event.preventDefault();
    zone.classList.remove('border-brand', 'bg-blue-50');
    if (event.dataTransfer.files[0]) setStreamingFile(event.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => {
    if (input.files[0]) setStreamingFile(input.files[0]);
  });
}

function setStreamingFile(file) {
  selectedStreamingFile = file;
  document.getElementById('streaming-file-prompt').classList.add('hidden');
  const info = document.getElementById('streaming-file-info');
  info.textContent = file.name;
  info.classList.remove('hidden');
  document.getElementById('streaming-message').classList.add('hidden');
}

async function uploadStreamingFile() {
  const start = document.getElementById('streaming-week-start').value;
  const end = document.getElementById('streaming-week-end').value;
  if (!selectedStreamingFile) return showStreamingMessage('Please select a CSV or XLSX file.', false);
  if (!start || !end) return showStreamingMessage('Please select both reporting week dates.', false);

  const button = document.getElementById('streaming-upload-btn');
  button.disabled = true;
  button.textContent = 'Processing...';
  const form = new FormData();
  form.append('file', selectedStreamingFile);
  form.append('week_start_date', start);
  form.append('week_end_date', end);

  try {
    const response = await fetch(`${API}/streaming/apple-music/upload`, {
      method: 'POST', headers: authHeaders(), body: form
    });
    const data = await response.json();
    if (!response.ok) {
      showStreamingMessage(data.detail || 'Upload failed.', false);
      return;
    }
    showStreamingMessage(`Uploaded ${data.original_filename}. It is ready for your processing pipeline.`, true);
    await loadStreamingHistory();
  } catch (error) {
    showStreamingMessage('Could not connect to the server.', false);
  } finally {
    button.disabled = false;
    button.textContent = 'Upload Apple Music Data';
  }
}

function showStreamingMessage(message, success) {
  const element = document.getElementById('streaming-message');
  element.textContent = message;
  element.className = `mb-4 px-4 py-3 rounded-lg text-sm ${success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`;
}

async function loadStreamingHistory() {
  const body = document.getElementById('streaming-history-body');
  try {
    const response = await fetch(`${API}/streaming/apple-music/recent`, { headers: authHeaders() });
    if (!response.ok) return;
    const uploads = await response.json();
    body.innerHTML = uploads.length ? uploads.map(upload => `
      <tr class="border-b border-gray-50">
        <td class="px-4 py-3 text-sm text-gray-700">${escapeHtml(upload.original_filename)}</td>
        <td class="px-4 py-3 text-sm text-gray-500">${upload.week_start_date} – ${upload.week_end_date}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${escapeHtml(upload.uploaded_by)}</td>
        <td class="px-4 py-3 text-sm text-blue-700">${escapeHtml(upload.status)}</td>
      </tr>`).join('') : '<tr><td colspan="4" class="px-4 py-8 text-center text-sm text-gray-400">No Apple Music uploads yet.</td></tr>';
  } catch (error) {
    body.innerHTML = '<tr><td colspan="4" class="px-4 py-8 text-center text-sm text-red-500">Could not load recent uploads.</td></tr>';
  }
  await Promise.all([loadABCoverage(), loadABRuns()]);
}

async function streamingPlatformChanged() {
  const audiomack = document.getElementById('ab-platform').value === 'audiomack';
  document.getElementById('ab-countries-wrap').classList.toggle('hidden', !audiomack);
  await loadABCoverage();
  if (audiomack) await loadAudiomackCountries();
}

async function loadABCoverage() {
  const platform = document.getElementById('ab-platform')?.value;
  if (!platform) return;
  const label = document.getElementById('ab-coverage');
  try {
    const response = await fetch(`${API}/streaming/${platform}/coverage`, { headers: authHeaders() });
    if (!response.ok) throw new Error();
    const coverage = await response.json();
    if (!coverage.earliest_date) {
      label.textContent = `No ${platform} data has been loaded yet.`;
      return;
    }
    label.textContent = `Available ${coverage.earliest_date} to ${coverage.latest_date}` +
      (coverage.missing_dates.length ? ` · ${coverage.missing_dates.length} missing date(s)` : ' · Complete coverage');
    for (const id of ['ab-start-date', 'ab-end-date']) {
      const input = document.getElementById(id);
      input.min = coverage.earliest_date;
      input.max = coverage.latest_date;
    }
  } catch (error) {
    label.textContent = 'Could not load platform coverage.';
  }
}

async function loadAudiomackCountries() {
  if (document.getElementById('ab-platform')?.value !== 'audiomack') return;
  const start = document.getElementById('ab-start-date').value;
  const end = document.getElementById('ab-end-date').value;
  const options = document.getElementById('ab-countries-options');
  if (!start || !end || end < start) {
    options.innerHTML = '<p class="px-2 py-2 text-sm text-gray-400">Select a date range first.</p>';
    updateCountryDropdownSummary();
    return;
  }
  try {
    const response = await fetch(`${API}/streaming/audiomack/countries?start_date=${start}&end_date=${end}`, { headers: authHeaders() });
    const countries = response.ok ? await response.json() : [];
    options.innerHTML = countries.length ? countries.map(country => `
      <label class="flex items-center gap-2 px-2 py-2 rounded-md hover:bg-gray-50 cursor-pointer text-sm text-gray-700">
        <input type="checkbox" value="${escapeHtml(country)}" onchange="updateCountryDropdownSummary()" class="ab-country-option rounded border-gray-300 text-brand focus:ring-brand" />
        <span>${escapeHtml(country)}</span>
      </label>`).join('') : '<p class="px-2 py-2 text-sm text-gray-400">No countries available for this period.</p>';
    updateCountryDropdownSummary();
  } catch (error) {
    options.innerHTML = '<p class="px-2 py-2 text-sm text-red-500">Could not load countries.</p>';
    updateCountryDropdownSummary();
  }
}

function selectedAudiomackCountries() {
  return Array.from(document.querySelectorAll('.ab-country-option:checked')).map(input => input.value);
}

function updateCountryDropdownSummary() {
  const countries = selectedAudiomackCountries();
  const summary = document.getElementById('ab-countries-summary');
  if (!summary) return;
  summary.textContent = countries.length ? countries.join(', ') : 'Select countries';
  summary.className = countries.length ? 'text-gray-800' : 'text-gray-500';
}

function showABMessage(message, success) {
  const element = document.getElementById('ab-message');
  element.textContent = message;
  element.className = `mb-4 px-4 py-3 rounded-lg text-sm ${success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`;
}

async function downloadStreamingExport() {
  const platform = document.getElementById('ab-platform').value;
  const start = document.getElementById('ab-start-date').value;
  const end = document.getElementById('ab-end-date').value;
  if (!start || !end || end < start) return showABMessage('Select a valid start and end date.', false);
  const params = new URLSearchParams({ start_date: start, end_date: end });
  if (platform === 'audiomack') {
    const countries = selectedAudiomackCountries();
    if (!countries.length) return showABMessage('Select at least one country.', false);
    countries.forEach(country => params.append('countries', country));
  }
  const button = document.getElementById('ab-download-btn');
  button.disabled = true;
  button.textContent = 'Preparing report...';
  try {
    const response = await fetch(`${API}/streaming/${platform}/export?${params}`, { headers: authHeaders() });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Download failed.');
    }
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const filename = match ? decodeURIComponent(match[1]) : `${platform}_${start}_${end}.xlsx`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    showABMessage(`Downloaded ${filename}.`, true);
  } catch (error) {
    showABMessage(error.message || 'Download failed.', false);
  } finally {
    button.disabled = false;
    button.textContent = 'Download report';
  }
}

async function loadABRuns() {
  const body = document.getElementById('ab-runs-body');
  if (!body) return;
  try {
    const response = await fetch(`${API}/streaming/audiomack-boomplay/ingestion-runs`, { headers: authHeaders() });
    if (!response.ok) throw new Error();
    const runs = await response.json();
    body.innerHTML = runs.length ? runs.map(run => `
      <tr class="border-b border-gray-50">
        <td class="px-4 py-3 text-sm text-gray-700 capitalize">${escapeHtml(run.platform)}</td>
        <td class="px-4 py-3 text-sm text-gray-500">${run.week_start_date} – ${run.week_end_date}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${run.loaded_file_count}/${run.expected_file_count}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${Number(run.loaded_row_count).toLocaleString()}</td>
        <td class="px-4 py-3 text-sm ${run.status === 'succeeded' ? 'text-green-700' : run.status === 'partial' ? 'text-amber-700' : 'text-red-700'}">${escapeHtml(run.status)}</td>
      </tr>`).join('') : '<tr><td colspan="5" class="px-4 py-8 text-center text-sm text-gray-400">No ingestion runs yet.</td></tr>';
  } catch (error) {
    body.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-sm text-red-500">Could not load ingestion history.</td></tr>';
  }
}

function showBackfillMessage(message, success) {
  const element = document.getElementById('backfill-message');
  element.textContent = message;
  element.className = `mb-4 px-4 py-3 rounded-lg text-sm ${success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`;
}

function showConfigurationTab(tab) {
  const backfill = tab === 'backfill';
  document.getElementById('configuration-backfill-panel').classList.toggle('hidden', !backfill);
  document.getElementById('configuration-users-panel').classList.toggle('hidden', backfill);
  document.getElementById('configuration-backfill-tab').className = configurationTabClass(backfill);
  document.getElementById('configuration-users-tab').className = configurationTabClass(!backfill);
  if (backfill) loadConfigurationRuns();
}

function configurationTabClass(active) {
  return `pb-3 border-b-2 text-sm font-medium ${active ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-800'}`;
}

async function runStreamingBackfill() {
  const start = document.getElementById('backfill-start-date').value;
  const end = document.getElementById('backfill-end-date').value;
  if (!start || !end) return showBackfillMessage('Select both start and end dates.', false);
  if (end < start) return showBackfillMessage('End date must be on or after start date.', false);

  const button = document.getElementById('backfill-run-btn');
  button.disabled = true;
  button.textContent = 'Queuing backfill...';
  try {
    const params = new URLSearchParams({ start_date: start, end_date: end });
    const response = await fetch(`${API}/streaming/audiomack-boomplay/backfill?${params}`, {
      method: 'POST', headers: authHeaders()
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Backfill could not be started.');
    showBackfillMessage(`Backfill accepted for ${data.start_date} to ${data.end_date}. Refresh activity to follow each chunk.`, true);
    setTimeout(loadConfigurationRuns, 1500);
  } catch (error) {
    showBackfillMessage(error.message || 'Backfill could not be started.', false);
  } finally {
    button.disabled = false;
    button.textContent = 'Run backfill';
  }
}

async function loadConfigurationRuns() {
  if (currentUser?.role !== 'admin') return;
  const body = document.getElementById('configuration-runs-body');
  try {
    const response = await fetch(`${API}/streaming/audiomack-boomplay/ingestion-runs?limit=50`, { headers: authHeaders() });
    if (!response.ok) throw new Error();
    const runs = await response.json();
    body.innerHTML = runs.length ? runs.map(run => `
      <tr class="border-b border-gray-50">
        <td class="px-4 py-3 text-sm text-gray-700 capitalize">${escapeHtml(run.platform)}</td>
        <td class="px-4 py-3 text-sm text-gray-500">${run.week_start_date} – ${run.week_end_date}</td>
        <td class="px-4 py-3 text-sm text-gray-600 capitalize">${escapeHtml(run.trigger)}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${run.loaded_file_count}/${run.expected_file_count}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${Number(run.loaded_row_count).toLocaleString()}</td>
        <td class="px-4 py-3 text-sm ${run.status === 'succeeded' ? 'text-green-700' : run.status === 'partial' ? 'text-amber-700' : run.status === 'running' ? 'text-blue-700' : 'text-red-700'}">${escapeHtml(run.status)}</td>
      </tr>`).join('') : '<tr><td colspan="6" class="px-4 py-8 text-center text-sm text-gray-400">No ingestion activity yet.</td></tr>';
  } catch (error) {
    body.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-sm text-red-500">Could not load ingestion activity.</td></tr>';
  }
}

function showCreateUserMessage(message, success) {
  const element = document.getElementById('create-user-message');
  element.textContent = message;
  element.className = `mb-4 px-4 py-3 rounded-lg text-sm ${success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`;
}

async function createConfigurationUser() {
  const payload = {
    first_name: document.getElementById('create-user-first-name').value.trim(),
    last_name: document.getElementById('create-user-last-name').value.trim(),
    username: document.getElementById('create-user-username').value.trim(),
    email: document.getElementById('create-user-email').value.trim(),
    role: document.getElementById('create-user-role').value,
    password: document.getElementById('create-user-password').value,
  };
  const confirmation = document.getElementById('create-user-confirm-password').value;
  if (!payload.first_name || !payload.last_name || !payload.username || !payload.email || !payload.password) {
    return showCreateUserMessage('Complete all user fields.', false);
  }
  if (payload.password.length < 8) return showCreateUserMessage('Password must contain at least 8 characters.', false);
  if (payload.password !== confirmation) return showCreateUserMessage('Passwords do not match.', false);

  const button = document.getElementById('create-user-btn');
  button.disabled = true;
  button.textContent = 'Creating user...';
  try {
    const response = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map(error => error.msg).join(' ')
        : data.detail;
      throw new Error(detail || 'User could not be created.');
    }
    showCreateUserMessage(`${data.email} was created with the ${data.role} role.`, true);
    for (const id of [
      'create-user-first-name', 'create-user-last-name', 'create-user-username',
      'create-user-email', 'create-user-password', 'create-user-confirm-password'
    ]) document.getElementById(id).value = '';
    document.getElementById('create-user-role').value = 'user';
  } catch (error) {
    showCreateUserMessage(error.message || 'User could not be created.', false);
  } finally {
    button.disabled = false;
    button.textContent = 'Create user';
  }
}

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = String(value);
  return element.innerHTML;
}

function setSelectedFile(file) {
  selectedFile = file;
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-info').classList.remove('hidden');
  document.getElementById('dropzone-prompt').classList.add('hidden');
}

function clearFile() {
  selectedFile = null;
  if (fileInput) fileInput.value = '';
  document.getElementById('file-info').classList.add('hidden');
  document.getElementById('dropzone-prompt').classList.remove('hidden');
  resetUploadState();
}

function resetUploadState() {
  document.getElementById('upload-error').classList.add('hidden');
  document.getElementById('replacement-warning').classList.add('hidden');
  document.getElementById('upload-success').classList.add('hidden');
  document.getElementById('upload-success-text').textContent = 'File cleaned successfully — your download should have started.';
  pendingReplacementUpload = null;
  document.getElementById('upload-btn').disabled = false;
}

async function uploadFile(confirmReplacement = false) {
  const templateFilename = document.getElementById('template-select').value;
  const weekStartDate = document.getElementById('week-start-date').value;
  const weekEndDate = document.getElementById('week-end-date').value;
  const uploadContext = selectedFile ? {
    templateFilename,
    weekStartDate,
    weekEndDate,
    fileName: selectedFile.name,
    fileLastModified: selectedFile.lastModified,
  } : null;

  if (!templateFilename) {
    showUploadError('Please select a template before uploading.');
    return;
  }
  if (!selectedFile) {
    showUploadError('Please select a file to upload.');
    return;
  }
  if (!weekStartDate || !weekEndDate) {
    showUploadError('Please provide both week start and end dates.');
    return;
  }

  const btn = document.getElementById('upload-btn');
  btn.disabled = true;
  btn.textContent = 'Processing...';
  document.getElementById('upload-error').classList.add('hidden');
  document.getElementById('replacement-warning').classList.add('hidden');
  document.getElementById('upload-success').classList.add('hidden');
  document.getElementById('upload-success-text').textContent = 'File cleaned successfully — your download should have started.';

  try {
    const form = new FormData();
    form.append('file', selectedFile);
    form.append('template_name', templateFilename);
    form.append('week_start_date', weekStartDate);
    form.append('week_end_date', weekEndDate);
    form.append('confirm_replace', String(confirmReplacement));

    const res = await fetch(`${API}/clean/`, {
      method: 'POST',
      headers: authHeaders(),
      body: form
    });

    if (res.status === 409) {
      const err = await res.json();
      showReplacementWarning(
        err.detail || "This week's data has been processed in the past. Do you want to replace the DB data with this new version?",
        uploadContext,
      );
      return;
    }

    if (!res.ok) {
      const err = await res.json();
      showUploadError(err.detail || 'Processing failed.');
      return;
    }

    const replacedPreviousUpload = res.headers.get('X-Replaced-Previous-Upload') === 'true';

    // Trigger download
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const fnMatch = disposition.match(/filename=(.+)/);
    const outputName = fnMatch ? fnMatch[1] : 'cleaned_output.xlsx';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = outputName;
    a.click();
    URL.revokeObjectURL(url);

    showUploadSuccess(replacedPreviousUpload);
    await loadHistory();

  } catch (err) {
    showUploadError('Could not connect to the server.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Clean & Download';
  }
}

function showUploadError(msg) {
  const el = document.getElementById('upload-error');
  document.getElementById('upload-error-text').textContent = msg;
  document.getElementById('replacement-warning').classList.add('hidden');
  el.classList.remove('hidden');
}

function showReplacementWarning(msg, uploadContext) {
  pendingReplacementUpload = uploadContext;
  document.getElementById('replacement-warning-text').textContent = msg;
  document.getElementById('replacement-warning').classList.remove('hidden');
}

function proceedReplacementUpload() {
  if (!pendingReplacementUpload) return;
  const templateFilename = document.getElementById('template-select').value;
  const weekStartDate = document.getElementById('week-start-date').value;
  const weekEndDate = document.getElementById('week-end-date').value;
  const uploadChanged =
    !selectedFile ||
    pendingReplacementUpload.templateFilename !== templateFilename ||
    pendingReplacementUpload.weekStartDate !== weekStartDate ||
    pendingReplacementUpload.weekEndDate !== weekEndDate ||
    pendingReplacementUpload.fileName !== selectedFile.name ||
    pendingReplacementUpload.fileLastModified !== selectedFile.lastModified;

  pendingReplacementUpload = null;
  if (uploadChanged) {
    document.getElementById('replacement-warning').classList.add('hidden');
    showUploadError('Upload details changed. Please submit again before replacing existing DB data.');
    return;
  }

  uploadFile(true);
}

function cancelReplacementUpload() {
  pendingReplacementUpload = null;
  document.getElementById('replacement-warning').classList.add('hidden');
  showUploadError('Upload cancelled. Existing DB data was left unchanged.');
}

function showUploadSuccess(replacedPreviousUpload) {
  const message = replacedPreviousUpload
    ? "This week's data has been processed in the past, replacing the DB data with this new version. Your download should have started."
    : 'File cleaned successfully — your download should have started.';

  document.getElementById('upload-success-text').textContent = message;
  document.getElementById('upload-success').classList.remove('hidden');
}


window.addEventListener('load', () => {
  setupDropzone();
  setupStreamingDropzone();
  init();
});
