const app = document.querySelector('#app');
const toastRegion = document.querySelector('#toast-region');

const state = {
  user: null,
  data: { patients: [], queue: [], stats: {} },
  view: 'overview',
  modal: null,
  search: '',
  busy: false,
};

const iconPaths = {
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
  people: '<path d="M16 20v-1.6a3.4 3.4 0 0 0-3.4-3.4H6.4A3.4 3.4 0 0 0 3 18.4V20"/><circle cx="9.5" cy="7.5" r="3.5"/><path d="M17 11.5a3.5 3.5 0 0 0 0-6.8M21 20v-1.6a3.4 3.4 0 0 0-2.5-3.3"/>',
  queue: '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" stroke-width="3"/>',
  chart: '<path d="M4 19V5M4 19h17"/><path d="m7 15 4-4 3 2 6-7"/><path d="M16 6h4v4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  shield: '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5h6a1.5 1.5 0 0 0-1.5-1.5h-3A1.5 1.5 0 0 0 9 4.5ZM9 10h6M9 14h6M9 18h3"/>',
  medicine: '<path d="m10 3 11 11-7 7L3 10l7-7Z"/><path d="m8 5 11 11M7 14l3-3"/>',
  logout: '<path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/>',
  close: '<path d="m18 6-12 12M6 6l12 12"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/>',
  pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
};

function icon(name, className = '') {
  const shape = iconPaths[name] || iconPaths.info;
  return `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shape}</svg>`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function initials(name) {
  return String(name || '?').trim().split(/\s+/).slice(0, 2).map((part) => part[0] || '').join('').toUpperCase();
}

function formatDate(value) {
  if (!value) return '—';
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(parsed);
}

function roleName(role = '') {
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function patientById(id) {
  return state.data.patients.find((patient) => patient.id === Number(id));
}

function showToast(message, type = 'success') {
  const node = document.createElement('div');
  node.className = `toast ${type === 'error' ? 'error' : ''}`;
  node.innerHTML = `${icon(type === 'error' ? 'info' : 'check')}<span>${escapeHtml(message)}</span>`;
  toastRegion.append(node);
  window.setTimeout(() => node.remove(), 3800);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/login') {
      state.user = null;
      state.data = { patients: [], queue: [], stats: {} };
      state.modal = null;
      render();
    }
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

async function refreshData() {
  state.data = await request('/api/bootstrap');
  render();
}

function renderLogin() {
  return `<main class="login-page">
    <section class="login-brand-panel">
      <a class="brand" href="#" aria-label="MEDSYS home"><span class="brand-mark">${icon('heart')}</span><span><span class="brand-name">MEDSYS</span><span class="brand-caption">CARE OPERATIONS</span></span></a>
      <div class="login-promo">
        <div class="eyebrow">A calmer way to care</div>
        <h1>Good care starts with a clear picture.</h1>
        <p>Keep your team in sync with a simple view of the waiting room, patient records, and the work happening today.</p>
        <div class="login-feature-list"><span class="login-feature">${icon('queue')} Live patient queue</span><span class="login-feature">${icon('shield')} Role-based access</span></div>
      </div>
      <div class="login-footer">MEDSYS Hospital Queue · Secure local workspace</div>
    </section>
    <section class="login-form-side"><form class="login-form-card" data-form="login">
      <div class="eyebrow">Welcome back</div><h2>Sign in to MEDSYS</h2><p>Enter your staff credentials to continue to your workspace.</p>
      <div class="form-field"><label for="login-role">Your role</label><select class="form-control" name="role" id="login-role" required><option value="" disabled selected>Select your department</option><option value="receptionist">Receptionist</option><option value="doctor">Doctor</option><option value="pharmacist">Pharmacist</option></select></div>
      <div class="form-field"><label for="login-username">Username</label><input class="form-control" id="login-username" name="username" autocomplete="username" placeholder="Your staff username" required /></div>
      <div class="form-field"><label for="login-password">Password</label><input class="form-control" id="login-password" name="password" type="password" autocomplete="current-password" placeholder="Enter your password" required /></div>
      <button class="button login-submit" type="submit" ${state.busy ? 'disabled' : ''}>${state.busy ? 'Signing in…' : 'Sign in'} ${icon('arrow')}</button>
      <div class="login-help">${icon('lock')} Access is limited to authorized hospital staff. Your account role determines which records and actions are available.</div>
    </form></section>
  </main>`;
}

function navigation() {
  const items = [
    ['overview', 'Overview', 'grid'],
    ...(state.user.role !== 'pharmacist' ? [['queue', 'Patient queue', 'queue']] : []),
    ['patients', 'Patients', 'people'],
    ['insights', 'Insights', 'chart'],
  ];
  return items.map(([key, label, glyph]) => `<button class="nav-item ${state.view === key ? 'active' : ''}" data-action="navigate" data-view="${key}" ${state.view === key ? 'aria-current="page"' : ''}>${icon(glyph)}<span>${label}</span></button>`).join('');
}

function pageTitle() {
  return ({ overview: 'Overview', queue: 'Patient queue', patients: 'Patient records', insights: 'Insights' })[state.view] || 'Overview';
}

function shell(content) {
  const username = escapeHtml(state.user.username);
  const initialsText = escapeHtml(initials(state.user.username));
  const today = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date());
  return `<div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" aria-label="MEDSYS home"><span class="brand-mark">${icon('heart')}</span><span><span class="brand-name">MEDSYS</span><span class="brand-caption">CARE OPERATIONS</span></span></a>
      <div class="nav-label">Workspace</div><nav class="nav-list" aria-label="Main navigation">${navigation()}</nav>
      <div class="sidebar-spacer"></div>
      <div class="sidebar-note"><div class="sidebar-note-title">${icon('pulse')} Care, in sync</div><p>Every patient interaction, organized in one calm, clear workspace.</p></div>
      <div class="sidebar-user"><div class="avatar">${initialsText}</div><div class="user-copy"><div class="user-name">${username}</div><div class="user-role">${escapeHtml(roleName(state.user.role))}</div></div><button class="icon-button logout-button" title="Sign out" aria-label="Sign out" data-action="logout">${icon('logout')}</button></div>
    </aside>
    <section class="main-area"><header class="topbar"><div class="breadcrumb"><span>Workspace</span>${icon('chevron')}<strong>${escapeHtml(pageTitle())}</strong></div><div class="topbar-right"><div class="date-chip">${icon('calendar')}<span>${escapeHtml(today)}</span></div><span class="topbar-divider"></span><div class="topbar-user"><div class="avatar avatar-small">${initialsText}</div><span>${username}</span></div></div></header><main class="content">${content}</main></section>
    ${renderModal()}
  </div>`;
}

function metricCard(label, value, hint, glyph, color = 'var(--green)', wash = '#e9f5ee') {
  return `<article class="metric-card" style="--metric-color:${color};--metric-wash:${wash}"><div class="metric-top"><span>${escapeHtml(label)}</span><span class="metric-icon">${icon(glyph)}</span></div><div class="metric-value">${escapeHtml(value)}</div><div class="metric-hint">${escapeHtml(hint)}</div></article>`;
}

function patientCell(patient, subtitle = '') {
  return `<span class="patient-cell"><span class="avatar">${escapeHtml(initials(patient.name))}</span><span><span class="patient-cell-name">${escapeHtml(patient.name)}</span><span class="patient-cell-meta">${escapeHtml(subtitle || `Patient #${patient.id}`)}</span></span></span>`;
}

function emptyState(title, description, glyph = 'clipboard') {
  return `<div class="empty-state"><div><span class="empty-icon">${icon(glyph)}</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div></div>`;
}

function queueTable(queue, compact = false) {
  const canServe = state.user.role === 'doctor';
  const canRemove = state.user.role === 'receptionist' || state.user.role === 'doctor';
  if (!queue.length) return emptyState('The queue is clear', 'New arrivals will appear here as soon as they are added.', 'queue');
  const rows = queue.map((item) => {
    const patient = item.patient;
    const action = canServe
      ? `<button class="table-action" data-action="serve" data-id="${patient.id}">Serve patient</button>`
      : canRemove
        ? `<button class="table-action" data-action="remove-queue" data-id="${patient.id}">Remove</button>`
        : '<span class="id-text">Waiting</span>';
    return `<tr><td><span class="id-text">${String(item.position).padStart(2, '0')}</span></td><td><button class="row-link" data-action="patient-detail" data-id="${patient.id}">${patientCell(patient, `${patient.age} years · ${patient.gender === 'M' ? 'Male' : 'Female'}`)}</button></td><td><span class="priority-badge ${item.priority === 'emergency' ? 'priority-emergency' : 'priority-regular'}">${item.priority === 'emergency' ? 'Emergency' : 'Regular'}</span></td>${compact ? '' : `<td>${action}</td>`}</tr>`;
  }).join('');
  return `<div class="table-wrap"><table><thead><tr><th>Position</th><th>Patient</th><th>Priority</th>${compact ? '' : '<th>Action</th>'}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function dashboardView() {
  const stats = state.data.stats;
  const queue = state.data.queue;
  const canQueue = state.user.role !== 'pharmacist';
  const isPharmacy = state.user.role === 'pharmacist';
  const cards = isPharmacy
    ? metricCard('Registered patients', stats.patients || 0, 'In the patient directory', 'people') + metricCard('Prescriptions', stats.prescriptions || 0, 'Across all patient records', 'medicine', '#a8751e', '#fff3dd') + metricCard('Clinical encounters', stats.encounters || 0, 'Recorded by the care team', 'clipboard', '#5573a5', '#edf1fb') + metricCard('Encounters today', stats.today || 0, 'Recorded patient visits today', 'calendar', '#805cb0', '#f1ecf8')
    : metricCard('Registered patients', stats.patients || 0, 'In the patient directory', 'people') + metricCard('Waiting patients', stats.in_queue || 0, 'Currently in the queue', 'queue', '#5573a5', '#edf1fb') + metricCard('Emergency cases', stats.emergency || 0, 'Priority attention needed', 'pulse', '#bf5652', '#fff0ef') + metricCard('Seen today', stats.today || 0, 'Encounters recorded today', 'calendar', '#a8751e', '#fff3dd');
  const recentPatients = [...state.data.patients].sort((a, b) => b.id - a.id).slice(0, 5);
  const queueActions = canQueue && state.user.role === 'receptionist' ? `<button class="button button-secondary button-small" data-action="queue-existing">${icon('plus')} Add patient</button>` : '';
  const recentRows = recentPatients.length ? recentPatients.map((patient) => `<div class="quick-row"><div class="quick-left"><button class="row-link" data-action="patient-detail" data-id="${patient.id}">${patientCell(patient, `${patient.age} years · ${patient.gender === 'M' ? 'Male' : 'Female'}`)}</button></div><span class="quick-number">#${patient.id}</span></div>`).join('') : emptyState('No patients yet', 'Register a patient to start building your directory.', 'people');
  return `<div class="page-heading"><div><div class="eyebrow">${escapeHtml(roleName(state.user.role))} workspace</div><h1>${greeting()}, ${escapeHtml(state.user.username)}</h1><p>Here’s the latest picture of care across your department.</p></div>${state.user.role === 'receptionist' ? `<div class="heading-actions"><button class="button" data-action="new-patient">${icon('plus')} Register patient</button></div>` : ''}</div>
    <section class="metrics-grid" aria-label="Key metrics">${cards}</section>
    <section class="dashboard-grid">
      ${canQueue ? `<article class="panel"><header class="panel-header"><div><h2 class="panel-title">Live patient queue</h2><p class="panel-subtitle">${queue.length ? `${queue.length} patient${queue.length === 1 ? '' : 's'} waiting for care` : 'Patients waiting to be seen'}</p></div><div class="heading-actions">${queueActions}<button class="link-button" data-action="navigate" data-view="queue">View queue ${icon('chevron')}</button></div></header><div class="panel-body">${queueTable(queue.slice(0, 5), false)}</div></article>` : `<article class="panel"><header class="panel-header"><div><h2 class="panel-title">Recently added patients</h2><p class="panel-subtitle">Latest additions to the patient directory</p></div><button class="link-button" data-action="navigate" data-view="patients">View all ${icon('chevron')}</button></header><div class="panel-body"><div class="quick-list">${recentRows}</div></div></article>`}
      <article class="panel"><header class="panel-header"><div><h2 class="panel-title">${canQueue ? 'Recently registered' : 'Pharmacy overview'}</h2><p class="panel-subtitle">${canQueue ? 'Latest additions to the patient directory' : 'Prescription records are ready to review'}</p></div>${canQueue ? `<button class="link-button" data-action="navigate" data-view="patients">View all ${icon('chevron')}</button>` : ''}</header><div class="panel-body">${canQueue ? `<div class="quick-list">${recentRows}</div>` : `<div class="insight-callout">${icon('medicine', 'insight-callout-icon')}<div><strong>${stats.prescriptions || 0} prescriptions on file</strong><p>Open patient records to review medication details.</p></div></div><button class="button button-secondary button-small" style="margin:15px 0 5px" data-action="navigate" data-view="patients">Browse patient records ${icon('arrow')}</button>`}</div></article>
    </section>`;
}

function queueView() {
  const queue = state.data.queue;
  const urgent = queue.filter((item) => item.priority === 'emergency').length;
  const waiting = queue.length - urgent;
  return `<div class="page-heading"><div><div class="eyebrow">Front desk · care team</div><h1>Patient queue</h1><p>Keep arrivals moving with a clear, up-to-date waiting list.</p></div>${state.user.role === 'receptionist' ? `<button class="button" data-action="queue-existing">${icon('plus')} Add to queue</button>` : ''}</div>
    <section class="metrics-grid">${metricCard('Waiting now', queue.length, 'Patients in active queue', 'queue', '#5573a5', '#edf1fb')}${metricCard('Emergency', urgent, 'Requires priority attention', 'pulse', '#bf5652', '#fff0ef')}${metricCard('Regular', waiting, 'In arrival order', 'clock', '#a8751e', '#fff3dd')}${metricCard('Patient directory', state.data.stats.patients || 0, 'Registered patient records', 'people')}</section>
    <article class="panel table-panel"><header class="panel-header"><div><h2 class="panel-title">Waiting list</h2><p class="panel-subtitle">Emergency cases are moved to the front of the queue.</p></div><span class="status-badge">${queue.length} active</span></header><div class="panel-body">${queueTable(queue)}</div></article>`;
}

function filteredPatients() {
  const query = state.search.trim().toLowerCase();
  const patients = [...state.data.patients].sort((a, b) => a.name.localeCompare(b.name));
  return query ? patients.filter((patient) => `${patient.name} ${patient.id}`.toLowerCase().includes(query)) : patients;
}

function patientTable(patients) {
  if (!patients.length) return emptyState(state.data.patients.length ? 'No matching patients' : 'No patient records yet', state.data.patients.length ? 'Try another name or patient ID.' : 'New patient registrations will appear in this directory.', 'people');
  const pharmacist = state.user.role === 'pharmacist';
  const rows = patients.map((patient) => {
    const detail = pharmacist ? `${patient.prescriptions.length} prescription${patient.prescriptions.length === 1 ? '' : 's'}` : `${patient.history.length} encounter${patient.history.length === 1 ? '' : 's'}`;
    const status = state.data.queue.some((item) => item.patient.id === patient.id)
      ? '<span class="status-badge amber">In queue</span>'
      : '<span class="id-text">Registered</span>';
    return `<tr><td><button class="row-link" data-action="patient-detail" data-id="${patient.id}">${patientCell(patient, `${patient.age} years · ${patient.gender === 'M' ? 'Male' : 'Female'}`)}</button></td><td><span class="id-text">#${patient.id}</span></td><td>${escapeHtml(detail)}</td><td>${status}</td><td><button class="table-action" data-action="patient-detail" data-id="${patient.id}">View record</button></td></tr>`;
  }).join('');
  return `<div class="table-wrap"><table><thead><tr><th>Patient</th><th>Patient ID</th><th>${pharmacist ? 'Prescriptions' : 'Encounters'}</th><th>Status</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function patientsView() {
  const patients = filteredPatients();
  const countLabel = `${patients.length} patient${patients.length === 1 ? '' : 's'}`;
  return `<div class="page-heading"><div><div class="eyebrow">Patient directory</div><h1>Patient records</h1><p>Find a patient and review the details relevant to your role.</p></div>${state.user.role === 'receptionist' ? `<button class="button" data-action="new-patient">${icon('plus')} Register patient</button>` : ''}</div>
    <article class="panel table-panel"><div class="toolbar"><div class="toolbar-left"><label class="search-box">${icon('search')}<input type="search" name="patient-search" value="${escapeHtml(state.search)}" placeholder="Search by patient name or ID…" aria-label="Search patients" /></label><span class="results-count">${countLabel}</span></div></div><div class="panel-body" id="patient-table">${patientTable(patients)}</div></article>`;
}

function aggregateRecords() {
  const actions = new Map();
  const medicines = new Map();
  state.data.patients.forEach((patient) => {
    patient.history.forEach((record) => actions.set(record.action, (actions.get(record.action) || 0) + 1));
    patient.prescriptions.forEach((record) => medicines.set(record.medicine, (medicines.get(record.medicine) || 0) + 1));
  });
  return {
    actions: [...actions.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
    medicines: [...medicines.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
  };
}

function barList(entries, fallback) {
  if (!entries.length) return emptyState(fallback, 'Records will appear here as your team uses MEDSYS.', 'chart');
  const max = Math.max(...entries.map((entry) => entry[1]), 1);
  return `<div class="bar-list">${entries.map(([label, count]) => `<div><div class="bar-heading"><span>${escapeHtml(label)}</span><strong>${count}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(7, count / max * 100)}%"></div></div></div>`).join('')}</div>`;
}

function insightsView() {
  const { actions, medicines } = aggregateRecords();
  const role = state.user.role;
  const leftTitle = role === 'pharmacist' ? 'Most prescribed medicines' : 'Most common encounters';
  const leftEntries = role === 'pharmacist' ? medicines : actions;
  const secondEntries = role === 'pharmacist' ? [] : medicines;
  const secondTitle = role === 'pharmacist' ? 'Patient activity' : 'Prescription activity';
  const secondContent = role === 'pharmacist'
    ? `<div class="insight-callout">${icon('people', 'insight-callout-icon')}<div><strong>${state.data.stats.patients || 0} patients in directory</strong><p>${state.data.stats.prescriptions || 0} prescription records available for review.</p></div></div>`
    : barList(secondEntries, 'No prescriptions yet');
  return `<div class="page-heading"><div><div class="eyebrow">Department snapshot</div><h1>Insights</h1><p>A quick overview of records and care activity in MEDSYS.</p></div><span class="status-badge">Updated just now</span></div>
    <section class="metrics-grid">${metricCard('Patients', state.data.stats.patients || 0, 'Registered in MEDSYS', 'people')}${metricCard('Encounters', state.data.stats.encounters || 0, 'Clinical history records', 'clipboard', '#5573a5', '#edf1fb')}${metricCard('Prescriptions', state.data.stats.prescriptions || 0, 'Medication records', 'medicine', '#a8751e', '#fff3dd')}${metricCard(role === 'pharmacist' ? 'Encounters today' : 'Seen today', state.data.stats.today || 0, 'Recorded patient visits today', 'calendar', '#805cb0', '#f1ecf8')}</section>
    <section class="insight-grid"><article class="insight-card"><h2>${escapeHtml(leftTitle)}</h2><p>${role === 'pharmacist' ? 'Based on available prescription records' : 'Based on recorded encounter types'}</p>${barList(leftEntries, 'No activity recorded yet')}</article><article class="insight-card"><h2>${escapeHtml(secondTitle)}</h2><p>${role === 'pharmacist' ? 'Directory at a glance' : 'Based on medication records'}</p>${secondContent}</article></section>`;
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

function renderModal() {
  if (!state.modal) return '';
  const modal = state.modal;
  if (modal.type === 'patient-detail') return patientDetailModal(patientById(modal.id));
  if (modal.type === 'patient-create') return patientFormModal('create');
  if (modal.type === 'patient-edit') return patientFormModal('edit', patientById(modal.id));
  if (modal.type === 'queue-existing') return queueModal();
  if (modal.type === 'serve') return serveModal(patientById(modal.id));
  return '';
}

function patientDetailModal(patient) {
  if (!patient) return '';
  const pharmacist = state.user.role === 'pharmacist';
  const queued = state.data.queue.some((item) => item.patient.id === patient.id);
  const historyBlock = pharmacist ? '' : `<section class="record-section"><h3>Encounter history <span class="id-text">${patient.history.length} record${patient.history.length === 1 ? '' : 's'}</span></h3>${patient.history.length ? patient.history.map((record) => `<div class="record-item"><strong>${escapeHtml(record.action)}</strong><p>${escapeHtml(record.result)}</p><span>${escapeHtml(formatDate(record.date))} · ${escapeHtml(record.doctor)}</span></div>`).join('') : emptyState('No encounters recorded', 'Clinical notes will appear here after a patient is seen.', 'clipboard')}</section>`;
  const prescriptionBlock = pharmacist ? `<section class="record-section"><h3>Prescriptions <span class="id-text">${patient.prescriptions.length} record${patient.prescriptions.length === 1 ? '' : 's'}</span></h3>${patient.prescriptions.length ? patient.prescriptions.map((record) => `<div class="record-item"><strong>${escapeHtml(record.medicine)} · ${escapeHtml(record.dosage)}</strong><p>${escapeHtml(record.instructions)}</p><span>${escapeHtml(formatDate(record.date))} · ${escapeHtml(record.doctor)}</span></div>`).join('') : emptyState('No prescriptions on file', 'Medication records will appear here when they are available.', 'medicine')}</section>` : '';
  const detailsActions = [
    !pharmacist && `<button class="button button-secondary button-small" data-action="edit-patient" data-id="${patient.id}">${icon('edit')} Edit details</button>`,
    state.user.role === 'receptionist' && !queued && `<button class="button button-secondary button-small" data-action="queue-patient" data-id="${patient.id}">${icon('plus')} Add to queue</button>`,
    state.user.role === 'doctor' && queued && `<button class="button button-small" data-action="serve" data-id="${patient.id}">${icon('check')} Serve patient</button>`,
    !pharmacist && `<button class="button button-quiet button-small" data-action="delete-patient" data-id="${patient.id}">${icon('trash')} Delete record</button>`,
  ].filter(Boolean).join('');
  return `<div class="modal-backdrop" data-action="backdrop"><section class="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">Patient record</h2><p>Review patient details and recorded care.</p></div><button class="icon-button modal-close" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></header><div class="modal-body"><div class="patient-detail-head"><span class="avatar">${escapeHtml(initials(patient.name))}</span><div><div class="patient-detail-name">${escapeHtml(patient.name)}</div><div class="patient-detail-meta">Patient #${patient.id} · ${patient.age} years old · ${patient.gender === 'M' ? 'Male' : 'Female'}</div></div></div>${historyBlock}${prescriptionBlock}</div>${detailsActions ? `<footer class="modal-footer" style="justify-content:flex-start"><div class="detail-actions">${detailsActions}</div></footer>` : ''}</section></div>`;
}

function patientFormModal(mode, patient = null) {
  if (mode === 'edit' && !patient) return '';
  const editing = mode === 'edit';
  const title = editing ? 'Edit patient details' : 'Register a patient';
  const subtitle = editing ? `Update the details for patient #${patient.id}.` : 'Add a patient to the directory and optionally the queue.';
  return `<div class="modal-backdrop" data-action="backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">${title}</h2><p>${subtitle}</p></div><button class="icon-button modal-close" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></header><form data-form="${editing ? 'patient-edit' : 'patient-create'}" data-id="${editing ? patient.id : ''}"><div class="modal-body"><div class="form-grid"><div class="form-field"><label for="patient-first">First name</label><input class="form-control" id="patient-first" name="first" maxlength="60" value="${editing ? escapeHtml(patient.first) : ''}" required /></div><div class="form-field"><label for="patient-middle">Middle name <span class="id-text">(optional)</span></label><input class="form-control" id="patient-middle" name="middle" maxlength="60" value="${editing ? escapeHtml(patient.middle) : ''}" /></div><div class="form-field"><label for="patient-last">Last name</label><input class="form-control" id="patient-last" name="last" maxlength="60" value="${editing ? escapeHtml(patient.last) : ''}" required /></div><div class="form-field"><label for="patient-age">Age</label><input class="form-control" id="patient-age" name="age" type="number" min="0" max="150" value="${editing ? patient.age : ''}" required /></div><div class="form-field"><label for="patient-gender">Gender</label><select class="form-control" id="patient-gender" name="gender" required><option value="" disabled ${editing ? '' : 'selected'}>Select</option><option value="F" ${editing && patient.gender === 'F' ? 'selected' : ''}>Female</option><option value="M" ${editing && patient.gender === 'M' ? 'selected' : ''}>Male</option></select></div>${!editing ? `<div class="form-field"><label for="patient-priority">Add to queue</label><select class="form-control" id="patient-priority" name="priority"><option value="">Not now</option><option value="Regular">Regular</option><option value="emergency">Emergency</option></select></div>` : ''}</div><p class="form-note">Patient names can include letters, spaces, apostrophes, and hyphens. Patient records are stored in the MEDSYS data file.</p></div><footer class="modal-footer"><button class="button button-secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit" ${state.busy ? 'disabled' : ''}>${state.busy ? 'Saving…' : editing ? 'Save changes' : 'Register patient'}</button></footer></form></section></div>`;
}

function queueModal() {
  const patientOptions = [...state.data.patients].sort((a, b) => a.name.localeCompare(b.name)).map((patient) => `<option value="${patient.id}">${escapeHtml(patient.name)} · #${patient.id}${state.data.queue.some((item) => item.patient.id === patient.id) ? ' (already queued)' : ''}</option>`).join('');
  return `<div class="modal-backdrop" data-action="backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">Add patient to queue</h2><p>Choose a registered patient and a priority.</p></div><button class="icon-button modal-close" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></header><form data-form="queue-existing"><div class="modal-body"><div class="form-field"><label for="queue-patient">Patient</label><select class="form-control" id="queue-patient" name="patient_id" required><option value="" disabled selected>Select a patient</option>${patientOptions}</select></div><div class="form-field"><label for="queue-priority">Priority</label><select class="form-control" id="queue-priority" name="priority" required><option value="Regular">Regular</option><option value="emergency">Emergency</option></select></div>${state.data.patients.length ? '' : '<p class="form-note">Register a patient before adding someone to the queue.</p>'}</div><footer class="modal-footer"><button class="button button-secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit" ${state.busy || !state.data.patients.length ? 'disabled' : ''}>Add to queue</button></footer></form></section></div>`;
}

function serveModal(patient) {
  if (!patient) return '';
  return `<div class="modal-backdrop" data-action="backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">Record encounter</h2><p>${escapeHtml(patient.name)} · patient #${patient.id}</p></div><button class="icon-button modal-close" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></header><form data-form="serve" data-id="${patient.id}"><div class="modal-body"><div class="form-field"><label for="encounter-action">Encounter type</label><input class="form-control" id="encounter-action" name="action" maxlength="200" placeholder="e.g. General consultation" required /></div><div class="form-field"><label for="encounter-result">Outcome / notes</label><textarea class="form-control" id="encounter-result" name="result" maxlength="500" placeholder="Document the outcome of this visit" required></textarea></div><label class="checkbox-row"><input type="checkbox" name="add-prescription" /> Add a prescription to this record</label><div class="form-grid prescription-fields" hidden><div class="form-field"><label for="prescription-medicine">Medicine</label><input class="form-control" id="prescription-medicine" name="medicine" maxlength="150" /></div><div class="form-field"><label for="prescription-dosage">Dosage</label><input class="form-control" id="prescription-dosage" name="dosage" maxlength="150" placeholder="e.g. 500 mg" /></div><div class="form-field full-width"><label for="prescription-instructions">Instructions</label><textarea class="form-control" id="prescription-instructions" name="instructions" maxlength="500" placeholder="How and when to take this medicine"></textarea></div></div></div><footer class="modal-footer"><button class="button button-secondary" type="button" data-action="close-modal">Cancel</button><button class="button" type="submit" ${state.busy ? 'disabled' : ''}>Complete encounter</button></footer></form></section></div>`;
}

function render() {
  if (!state.user) {
    app.innerHTML = renderLogin();
    return;
  }
  const content = ({ overview: dashboardView, queue: queueView, patients: patientsView, insights: insightsView })[state.view]();
  app.innerHTML = shell(content);
}

function setFormBusy(form, busy, label = 'Saving…') {
  const button = form.querySelector('button[type="submit"]');
  if (!button) return;
  if (busy) {
    button.dataset.defaultHtml = button.innerHTML;
    button.disabled = true;
    button.textContent = label;
  } else {
    button.disabled = false;
    if (button.dataset.defaultHtml) button.innerHTML = button.dataset.defaultHtml;
    delete button.dataset.defaultHtml;
  }
}

async function handleLogin(form) {
  const data = new FormData(form);
  state.busy = true;
  setFormBusy(form, true, 'Signing in…');
  try {
    const result = await request('/api/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(data.entries())) });
    state.user = result.user;
    state.view = 'overview';
    state.search = '';
    state.busy = false;
    await refreshData();
    showToast(`Welcome back, ${state.user.username}.`);
  } catch (error) {
    showToast(error.message, 'error');
    state.busy = false;
    setFormBusy(form, false);
  }
}

async function handleFormSubmit(form) {
  const formType = form.dataset.form;
  if (formType === 'login') return handleLogin(form);
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  state.busy = true;
  setFormBusy(form, true);
  try {
    if (formType === 'patient-create') {
      payload.age = Number(payload.age);
      await request('/api/patients', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Patient registered successfully.');
    } else if (formType === 'patient-edit') {
      payload.age = Number(payload.age);
      await request(`/api/patients/${form.dataset.id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Patient details updated.');
    } else if (formType === 'queue-existing') {
      await request(`/api/patients/${payload.patient_id}/queue`, { method: 'POST', body: JSON.stringify({ priority: payload.priority }) });
      showToast('Patient added to the queue.');
    } else if (formType === 'serve') {
      payload.patient_id = Number(form.dataset.id);
      if (formData.get('add-prescription') !== 'on') {
        delete payload.medicine;
        delete payload.dosage;
        delete payload.instructions;
      }
      delete payload['add-prescription'];
      await request('/api/serve', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Encounter recorded and patient served.');
    }
    state.modal = null;
    state.busy = false;
    await refreshData();
  } catch (error) {
    state.busy = false;
    setFormBusy(form, false);
    showToast(error.message, 'error');
  }
}

app.addEventListener('submit', (event) => {
  const form = event.target.closest('form[data-form]');
  if (!form) return;
  event.preventDefault();
  handleFormSubmit(form);
});

app.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action;
  if (action === 'navigate') {
    state.view = target.dataset.view;
    state.search = '';
    state.modal = null;
    render();
  } else if (action === 'new-patient') {
    state.modal = { type: 'patient-create' };
    render();
  } else if (action === 'queue-existing') {
    state.modal = { type: 'queue-existing' };
    render();
  } else if (action === 'queue-patient') {
    const patientId = target.dataset.id;
    state.modal = { type: 'queue-existing' };
    render();
    const patientSelect = app.querySelector('[name="patient_id"]');
    if (patientSelect) patientSelect.value = patientId;
  } else if (action === 'patient-detail') {
    state.modal = { type: 'patient-detail', id: Number(target.dataset.id) };
    render();
  } else if (action === 'edit-patient') {
    state.modal = { type: 'patient-edit', id: Number(target.dataset.id) };
    render();
  } else if (action === 'serve') {
    state.modal = { type: 'serve', id: Number(target.dataset.id) };
    render();
  } else if (action === 'close-modal' || (action === 'backdrop' && event.target === target)) {
    state.modal = null;
    render();
  } else if (action === 'remove-queue') {
    if (!window.confirm('Remove this patient from the active queue?')) return;
    try {
      await request(`/api/queue/${target.dataset.id}`, { method: 'DELETE' });
      showToast('Patient removed from the queue.');
      await refreshData();
    } catch (error) {
      showToast(error.message, 'error');
    }
  } else if (action === 'delete-patient') {
    const patient = patientById(target.dataset.id);
    if (!patient || !window.confirm(`Delete the record for ${patient.name}? This also removes any active queue entry.`)) return;
    try {
      await request(`/api/patients/${patient.id}`, { method: 'DELETE' });
      state.modal = null;
      showToast('Patient record deleted.');
      await refreshData();
    } catch (error) {
      showToast(error.message, 'error');
    }
  } else if (action === 'logout') {
    try { await request('/api/logout', { method: 'POST', body: '{}' }); } catch { /* local session can still be cleared */ }
    state.user = null;
    state.data = { patients: [], queue: [], stats: {} };
    state.view = 'overview';
    state.modal = null;
    state.search = '';
    render();
  }
});

app.addEventListener('input', (event) => {
  if (event.target.name === 'patient-search') {
    state.search = event.target.value;
    const cursor = event.target.selectionStart;
    render();
    const replacement = app.querySelector('[name="patient-search"]');
    if (replacement) {
      replacement.focus();
      replacement.setSelectionRange(cursor, cursor);
    }
  }
});

app.addEventListener('change', (event) => {
  if (event.target.name === 'add-prescription') {
    const fields = app.querySelector('.prescription-fields');
    if (!fields) return;
    fields.hidden = !event.target.checked;
    fields.querySelectorAll('input, textarea').forEach((field) => {
      field.required = event.target.checked;
    });
  }
});

window.setInterval
async function init() {
  try {
    const session = await request('/api/session');
    state.user = session.user;
    if (state.user) await refreshData();
    else render();
  } catch (error) {
    render();
    showToast(error.message, 'error');
  }
}

window.setInterval(async () => {
  if (!state.user || state.modal || document.hidden) return;
  try {
    state.data = await request('/api/bootstrap');
    if (!app.querySelector(':focus')) render();
  } catch {
    // The request handler moves expired sessions back to the sign-in screen.
  }
}, 30_000);

init();
