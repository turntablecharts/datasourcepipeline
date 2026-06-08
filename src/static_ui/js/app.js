let currentUser = null;
let availableTemplates = [];

async function init() {
  requireAuth();
  await loadUser();
  await loadTemplates();
  await loadHistory();
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
      <a href="${API}/templates/download/${t.filename}"
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
  document.getElementById('upload-success').classList.add('hidden');
  document.getElementById('upload-btn').disabled = false;
}

async function uploadFile() {
  const templateFilename = document.getElementById('template-select').value;
  const weekStartDate = document.getElementById('week-start-date').value;
  const weekEndDate = document.getElementById('week-end-date').value;

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
  document.getElementById('upload-success').classList.add('hidden');

  try {
    const form = new FormData();
    form.append('file', selectedFile);
    form.append('template_name', templateFilename);
    form.append('week_start_date', weekStartDate);
    form.append('week_end_date', weekEndDate);

    const res = await fetch(`${API}/clean/`, {
      method: 'POST',
      headers: authHeaders(),
      body: form
    });

    if (!res.ok) {
      const err = await res.json();
      showUploadError(err.detail || 'Processing failed.');
      return;
    }

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

    document.getElementById('upload-success').classList.remove('hidden');
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
  el.classList.remove('hidden');
}


window.addEventListener('load', () => {
  setupDropzone();
  init();
});
