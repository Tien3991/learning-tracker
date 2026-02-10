// ===== Data Layer =====

const STORAGE_KEY = 'readingTracker';

function loadData() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      if (data && Array.isArray(data.books)) return data;
    }
  } catch {}
  return { books: [] };
}

function saveData(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function getBooks() {
  return loadData().books;
}

function getBookById(id) {
  return getBooks().find(b => b.id === id) || null;
}

function addBook(name, totalPages, startTime) {
  const data = loadData();
  const now = startTime || new Date().toISOString();
  const book = {
    id: 'book_' + Date.now(),
    name,
    totalPages,
    createdAt: now,
    checkpoints: [
      { id: 'cp_' + Date.now(), page: 0, timestamp: now }
    ]
  };
  data.books.push(book);
  saveData(data);
  return book;
}

function deleteBook(bookId) {
  const data = loadData();
  data.books = data.books.filter(b => b.id !== bookId);
  saveData(data);
}

function addCheckpoint(bookId, page, timestamp, notes) {
  const data = loadData();
  const book = data.books.find(b => b.id === bookId);
  if (!book) return null;
  const cp = {
    id: 'cp_' + Date.now(),
    page,
    timestamp: timestamp || new Date().toISOString()
  };
  if (notes) cp.notes = notes;
  book.checkpoints.push(cp);
  book.checkpoints.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  saveData(data);
  return cp;
}

function deleteCheckpoint(bookId, cpId) {
  const data = loadData();
  const book = data.books.find(b => b.id === bookId);
  if (!book) return;
  book.checkpoints = book.checkpoints.filter(c => c.id !== cpId);
  saveData(data);
}

function replaceAllData(newData) {
  saveData(newData);
}

// ===== HTML Escaping =====

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ===== Estimation =====

function computeEstimation(book) {
  const cps = book.checkpoints;
  const currentPage = cps.length ? cps[cps.length - 1].page : 0;
  const pagesRemaining = book.totalPages - currentPage;
  const percent = book.totalPages > 0 ? (currentPage / book.totalPages) * 100 : 0;

  if (cps.length < 2) {
    return {
      currentPage,
      percent,
      pagesRemaining,
      speed: null,
      hoursRemaining: null,
      eta: null,
      joke: true
    };
  }

  const t0 = new Date(cps[0].timestamp).getTime();
  const elapsedHours = (Date.now() - t0) / 3600000;
  const speed = Math.max(elapsedHours > 0 ? currentPage / elapsedHours : 0.001, 0.001);
  const hoursRemaining = pagesRemaining / speed;
  const eta = new Date(Date.now() + hoursRemaining * 3600000);

  return {
    currentPage,
    percent,
    pagesRemaining,
    speed,
    hoursRemaining,
    eta,
    joke: false,
    regressionSlope: speed,
    regressionIntercept: 0,
    t0
  };
}

function formatDuration(hours) {
  if (hours == null || hours > 876000) return '~100 years';
  if (hours < 0) return '—';
  const totalMinutes = Math.round(hours * 60);
  if (totalMinutes < 60) return totalMinutes + ' min';
  const days = Math.floor(hours / 24);
  const h = Math.floor(hours % 24);
  const m = Math.round((hours - Math.floor(hours)) * 60);
  if (days > 0) return days + 'd ' + h + 'h';
  return Math.floor(hours) + 'h ' + m + 'min';
}

function formatSpeed(speed) {
  if (speed == null) return '—';
  return speed.toFixed(1) + ' pages/hr';
}

function formatETA(date) {
  if (!date) return '~100 years';
  const now = new Date();
  const diff = date - now;
  if (diff > 876000 * 3600000) return '~100 years';
  return date.toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

// ===== DOM References =====

const bookListView = document.getElementById('book-list-view');
const bookDetailView = document.getElementById('book-detail-view');
const bookGrid = document.getElementById('book-grid');
const emptyState = document.getElementById('empty-state');
const addBookForm = document.getElementById('add-book-form');

const backBtn = document.getElementById('back-btn');
const detailBookName = document.getElementById('detail-book-name');
const detailProgressFill = document.getElementById('detail-progress-fill');
const detailPageCount = document.getElementById('detail-page-count');
const statSpeed = document.getElementById('stat-speed');
const statRemaining = document.getElementById('stat-remaining');
const statEta = document.getElementById('stat-eta');
const addCheckpointForm = document.getElementById('add-checkpoint-form');
const cpPageInput = document.getElementById('cp-page');
const cpTimeInput = document.getElementById('cp-time');
const checkpointTbody = document.getElementById('checkpoint-tbody');
const deleteBookBtn = document.getElementById('delete-book-btn');

const cpNotesInput = document.getElementById('cp-notes');
const clearBookStartTime = document.getElementById('clear-book-start-time');
const clearCpTime = document.getElementById('clear-cp-time');
const bookStartTimeInput = document.getElementById('book-start-time');

const exportBtn = document.getElementById('export-btn');
const importInput = document.getElementById('import-input');
const themeToggle = document.getElementById('theme-toggle');

const concealToggle = document.getElementById('conceal-toggle');
const concealOverlay = document.getElementById('conceal-overlay');

const modalOverlay = document.getElementById('modal-overlay');
const modalMessage = document.getElementById('modal-message');
const modalCancel = document.getElementById('modal-cancel');
const modalConfirm = document.getElementById('modal-confirm');
const toastContainer = document.getElementById('toast-container');

let currentBookId = null;
let chartInstance = null;
let concealed = false;

// ===== Toast =====

function showToast(message, isError) {
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' toast-error' : '');
  el.textContent = message;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ===== Modal =====

function showModal(message) {
  return new Promise(resolve => {
    modalMessage.textContent = message;
    modalOverlay.classList.remove('hidden');
    function cleanup(result) {
      modalOverlay.classList.add('hidden');
      modalConfirm.removeEventListener('click', onConfirm);
      modalCancel.removeEventListener('click', onCancel);
      modalOverlay.removeEventListener('click', onOverlay);
      resolve(result);
    }
    function onConfirm() { cleanup(true); }
    function onCancel() { cleanup(false); }
    function onOverlay(e) { if (e.target === modalOverlay) cleanup(false); }
    modalConfirm.addEventListener('click', onConfirm);
    modalCancel.addEventListener('click', onCancel);
    modalOverlay.addEventListener('click', onOverlay);
  });
}

// ===== Book List Rendering =====

function renderBookList() {
  const books = getBooks();
  bookGrid.innerHTML = '';

  if (books.length === 0) {
    emptyState.classList.remove('hidden');
    return;
  }
  emptyState.classList.add('hidden');

  for (const book of books) {
    const est = computeEstimation(book);
    const card = document.createElement('div');
    card.className = 'book-card';
    card.setAttribute('data-id', book.id);

    const etaText = est.joke ? '~100 years' : formatETA(est.eta);
    card.innerHTML = `
      <h3>${esc(book.name)}</h3>
      <p class="card-meta">${esc(String(est.currentPage))} / ${esc(String(book.totalPages))} pages</p>
      <div class="progress-bar">
        <div class="progress-fill" style="width:${est.percent.toFixed(1)}%"></div>
      </div>
      <div class="card-footer">
        <span>${est.percent.toFixed(0)}%</span>
        <span>ETA: ${esc(etaText)}</span>
      </div>
    `;
    card.addEventListener('click', () => openBookDetail(book.id));
    bookGrid.appendChild(card);
  }
}

// ===== Book Detail Rendering =====

function openBookDetail(bookId) {
  currentBookId = bookId;
  bookListView.classList.add('hidden');
  bookDetailView.classList.remove('hidden');
  renderBookDetail();
}

function closeBookDetail() {
  currentBookId = null;
  bookDetailView.classList.add('hidden');
  bookListView.classList.remove('hidden');
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }
  renderBookList();
}

function renderBookDetail() {
  const book = getBookById(currentBookId);
  if (!book) { closeBookDetail(); return; }

  const est = computeEstimation(book);

  detailBookName.textContent = book.name;
  detailProgressFill.style.width = est.percent.toFixed(1) + '%';
  detailPageCount.textContent = est.currentPage + ' / ' + book.totalPages + ' pages (' + est.percent.toFixed(0) + '%)';

  // Stats
  statSpeed.textContent = est.joke ? '—' : formatSpeed(est.speed);
  statRemaining.textContent = est.joke ? '~100 years' : formatDuration(est.hoursRemaining);
  statEta.textContent = est.joke ? '~100 years' : formatETA(est.eta);

  // Checkpoint page input max
  cpPageInput.max = book.totalPages;

  // Auto-fill time to now
  cpTimeInput.value = toLocalDatetimeString(new Date());
  cpTimeToggle.update();

  // Checkpoints table
  checkpointTbody.innerHTML = '';
  for (const cp of book.checkpoints) {
    const tr = document.createElement('tr');
    const dateStr = new Date(cp.timestamp).toLocaleString();
    tr.innerHTML = `
      <td>${esc(String(cp.page))}</td>
      <td>${esc(dateStr)}</td>
      <td>${esc(cp.notes || '')}</td>
      <td><button class="btn btn-danger btn-sm cp-delete-btn" data-cpid="${esc(cp.id)}">Delete</button></td>
    `;
    checkpointTbody.appendChild(tr);
  }

  // Chart
  renderChart(book, est);
}

function toLocalDatetimeString(date) {
  const y = date.getFullYear();
  const mo = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const h = String(date.getHours()).padStart(2, '0');
  const mi = String(date.getMinutes()).padStart(2, '0');
  return `${y}-${mo}-${d}T${h}:${mi}`;
}

// ===== Chart =====

function getThemeChartColors() {
  const style = getComputedStyle(document.documentElement);
  return {
    line: style.getPropertyValue('--chart-line').trim(),
    dot: style.getPropertyValue('--chart-dot').trim(),
    proj: style.getPropertyValue('--chart-proj').trim(),
    grid: style.getPropertyValue('--chart-grid').trim(),
    text: style.getPropertyValue('--chart-text').trim(),
  };
}

function renderChart(book, est) {
  const canvas = document.getElementById('reading-chart');
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  const colors = getThemeChartColors();
  const cps = book.checkpoints;

  // Actual data (include notes for chart labels)
  const actual = cps.map(cp => ({ x: new Date(cp.timestamp).getTime(), y: cp.page, notes: cp.notes || null }));

  const datasets = [
    {
      label: 'Progress',
      data: actual,
      showLine: true,
      borderColor: colors.line,
      backgroundColor: colors.dot,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2,
      tension: 0,
    }
  ];

  // Regression / projection line
  if (!est.joke && est.regressionSlope != null) {
    const t0 = est.t0;
    const slope = est.regressionSlope;
    const intercept = est.regressionIntercept;

    // Two points: first checkpoint time -> projected completion
    const startHours = 0;
    const endHours = (book.totalPages - intercept) / slope;
    const startTime = t0 + startHours * 3600000;
    const endTime = t0 + endHours * 3600000;

    datasets.push({
      label: 'Projection',
      data: [
        { x: startTime, y: Math.max(0, intercept) },
        { x: endTime, y: book.totalPages }
      ],
      showLine: true,
      borderColor: colors.proj,
      borderDash: [8, 4],
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 0,
    });
  }

  const noteLabelsPlugin = {
    id: 'noteLabels',
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const dataset = chart.data.datasets[0];
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.font = '11px sans-serif';
      ctx.fillStyle = colors.text;
      ctx.textAlign = 'center';
      meta.data.forEach((point, i) => {
        const note = dataset.data[i]?.notes;
        if (note) {
          ctx.fillText(note, point.x, point.y - 12);
        }
      });
      ctx.restore();
    }
  };

  chartInstance = new Chart(canvas, {
    type: 'scatter',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'time',
          time: { tooltipFormat: 'PPpp' },
          title: { display: true, text: 'Time', color: colors.text },
          ticks: { color: colors.text },
          grid: { color: colors.grid },
        },
        y: {
          min: 0,
          max: book.totalPages,
          title: { display: true, text: 'Pages', color: colors.text },
          ticks: { color: colors.text },
          grid: { color: colors.grid },
        }
      },
      plugins: {
        legend: {
          labels: { color: colors.text }
        }
      }
    },
    plugins: [noteLabelsPlugin]
  });
}

// ===== Event Handlers =====

// Add book
addBookForm.addEventListener('submit', e => {
  e.preventDefault();
  const nameInput = document.getElementById('book-name');
  const pagesInput = document.getElementById('book-pages');
  const startInput = document.getElementById('book-start-time');

  const name = nameInput.value.trim();
  const totalPages = parseInt(pagesInput.value, 10);

  if (!name) { showToast('Book name is required', true); return; }
  if (!totalPages || totalPages < 1) { showToast('Total pages must be a positive integer', true); return; }

  const startTime = startInput.value ? new Date(startInput.value).toISOString() : undefined;
  addBook(name, totalPages, startTime);
  addBookForm.reset();
  bookStartTimeInput.value = toLocalDatetimeString(new Date());
  bookStartToggle.update();
  renderBookList();
  showToast('Book added!');
});

// Back button
backBtn.addEventListener('click', closeBookDetail);

// Add checkpoint
addCheckpointForm.addEventListener('submit', e => {
  e.preventDefault();
  if (!currentBookId) return;
  const book = getBookById(currentBookId);
  if (!book) return;

  const page = parseInt(cpPageInput.value, 10);
  if (isNaN(page) || page < 0 || page > book.totalPages) {
    showToast('Page must be between 0 and ' + book.totalPages, true);
    return;
  }

  const timestamp = cpTimeInput.value ? new Date(cpTimeInput.value).toISOString() : undefined;
  const notes = cpNotesInput.value.trim();
  addCheckpoint(currentBookId, page, timestamp, notes);
  cpPageInput.value = '';
  cpNotesInput.value = '';
  renderBookDetail();
  showToast('Checkpoint added!');
});

// Delete checkpoint (event delegation)
checkpointTbody.addEventListener('click', async e => {
  const btn = e.target.closest('.cp-delete-btn');
  if (!btn) return;
  const cpId = btn.dataset.cpid;
  const confirmed = await showModal('Delete this checkpoint?');
  if (!confirmed) return;
  deleteCheckpoint(currentBookId, cpId);
  renderBookDetail();
  showToast('Checkpoint deleted');
});

// Delete book
deleteBookBtn.addEventListener('click', async () => {
  if (!currentBookId) return;
  const confirmed = await showModal('Delete this book and all its checkpoints? This cannot be undone.');
  if (!confirmed) return;
  deleteBook(currentBookId);
  showToast('Book deleted');
  closeBookDetail();
});

// ===== Conceal Mode =====

function setConceal(active) {
  concealed = active;
  document.body.classList.toggle('concealed', active);
  if (active) {
    const img = localStorage.getItem('readingTrackerCoverImage');
    concealOverlay.style.backgroundImage = img ? `url(${img})` : '';
    concealOverlay.classList.remove('hidden');
  } else {
    concealOverlay.classList.add('hidden');
  }
}

concealToggle.addEventListener('click', () => setConceal(!concealed));

document.addEventListener('paste', (e) => {
  if (!concealed) return;
  const items = e.clipboardData.items;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault();
      const blob = item.getAsFile();
      const reader = new FileReader();
      reader.onload = () => {
        localStorage.setItem('readingTrackerCoverImage', reader.result);
        concealOverlay.style.backgroundImage = `url(${reader.result})`;
      };
      reader.readAsDataURL(blob);
      break;
    }
  }
});

document.addEventListener('keydown', (e) => {
  if (!concealed) return;
  if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault();
    localStorage.removeItem('readingTrackerCoverImage');
    concealOverlay.style.backgroundImage = '';
  }
});

// ===== Export / Import =====

exportBtn.addEventListener('click', () => {
  const data = loadData();
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const dateStr = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = 'reading-tracker-' + dateStr + '.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('Data exported!');
});

importInput.addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;

  const confirmed = await showModal('Import will replace all current data. Continue?');
  if (!confirmed) {
    importInput.value = '';
    return;
  }

  try {
    const text = await file.text();
    const data = JSON.parse(text);

    // Validate structure
    if (!data || !Array.isArray(data.books)) throw new Error('Invalid format: missing books array');
    for (const book of data.books) {
      if (!book.id || !book.name || !book.totalPages || !Array.isArray(book.checkpoints)) {
        throw new Error('Invalid book entry: ' + (book.name || book.id || 'unknown'));
      }
    }

    replaceAllData(data);
    renderBookList();
    showToast('Data imported successfully!');
  } catch (err) {
    showToast('Import failed: ' + err.message, true);
  }

  importInput.value = '';
});

// ===== Theme =====

function getPreferredTheme() {
  const saved = localStorage.getItem('readingTrackerTheme');
  if (saved) return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('readingTrackerTheme', theme);
  // Re-render chart if visible
  if (currentBookId && chartInstance) {
    const book = getBookById(currentBookId);
    if (book) {
      const est = computeEstimation(book);
      renderChart(book, est);
    }
  }
}

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  applyTheme(current === 'dark' ? 'light' : 'dark');
});

// ===== Timestamp Toggle Buttons =====

function setupTimestampToggle(btn, input) {
  function update() {
    if (input.value) {
      btn.textContent = '×';
      btn.title = 'Clear';
    } else {
      btn.textContent = '↻';
      btn.title = 'Now';
    }
  }
  btn.addEventListener('click', () => {
    if (input.value) {
      input.value = '';
    } else {
      input.value = toLocalDatetimeString(new Date());
    }
    update();
  });
  update();
  return { update };
}

const bookStartToggle = setupTimestampToggle(clearBookStartTime, bookStartTimeInput);
const cpTimeToggle = setupTimestampToggle(clearCpTime, cpTimeInput);

// ===== Init =====

applyTheme(getPreferredTheme());
bookStartTimeInput.value = toLocalDatetimeString(new Date());
bookStartToggle.update();
renderBookList();

// ===== Auto-update estimation every 10 minutes =====
setInterval(() => {
  if (new Date().getMinutes() % 10 !== 0) return;
  if (!bookDetailView.classList.contains('hidden') && currentBookId) {
    renderBookDetail();
  } else if (!bookListView.classList.contains('hidden')) {
    renderBookList();
  }
}, 60000);
