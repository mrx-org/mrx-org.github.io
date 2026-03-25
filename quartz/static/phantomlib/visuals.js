// --- Tool log ---

var outputLog = '';
var activeViewer = null;

var consoleEl = document.getElementById('console-output');
var overlay = document.getElementById('viewerOverlay');
var viewerContent = document.getElementById('viewerContent');
var viewerSubtitle = document.getElementById('viewerSubtitle');

// --- Log helpers ---

function last7Lines(text) {
  if (!text) return '';
  var lines = text.trimEnd().split('\n');
  return lines.slice(-7).join('\n');
}

function updateConsole() {
  consoleEl.textContent = last7Lines(outputLog);
}

function appendLog(text) {
  outputLog += text;
  updateConsole();
  if (activeViewer === 'output') {
    viewerContent.textContent = outputLog;
  }
}

function clearLog() {
  outputLog = '';
  updateConsole();
  setOutputActive(false);
  if (activeViewer === 'output') {
    viewerContent.textContent = '';
  }
}

function setOutputActive(active) {
  if (active) {
    consoleEl.classList.add('active');
  } else {
    consoleEl.classList.remove('active');
  }
}

updateConsole();

// --- Viewer ---

function openViewer(source, subtitle) {
  activeViewer = source;
  viewerSubtitle.textContent = subtitle;
  viewerContent.textContent = outputLog;
  overlay.classList.add('visible');
}

function closeViewer() {
  activeViewer = null;
  overlay.classList.remove('visible');
}

consoleEl.addEventListener('click', function () {
  openViewer('output', 'OUTPUT');
});

document.getElementById('viewerClose').addEventListener('click', closeViewer);

overlay.addEventListener('click', function (e) {
  if (e.target === overlay) closeViewer();
});

// --- File picker ---

var archiveFile = document.getElementById('archiveFile');
var fileLabel = document.getElementById('fileLabel');
var btnUpload = document.getElementById('btnUpload');

archiveFile.addEventListener('change', function () {
  if (archiveFile.files.length > 0) {
    fileLabel.textContent = archiveFile.files[0].name;
    btnUpload.disabled = false;
  } else {
    fileLabel.textContent = 'no archive selected';
    btnUpload.disabled = true;
  }
});

// --- Phantom table ---

var phantomTableBody = document.getElementById('phantomTableBody');

function renderPhantomTable(entries) {
  phantomTableBody.innerHTML = '';
  if (entries.length === 0) {
    var tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="2" class="phantom-table-empty">no phantoms found</td>';
    phantomTableBody.appendChild(tr);
    return;
  }
  for (var i = 0; i < entries.length; i++) {
    var tr = document.createElement('tr');
    var tdName = document.createElement('td');
    tdName.textContent = entries[i][0];
    var tdDate = document.createElement('td');
    tdDate.textContent = entries[i][1];
    tr.appendChild(tdName);
    tr.appendChild(tdDate);
    phantomTableBody.appendChild(tr);
  }
}

function setPhantomTableLoading() {
  phantomTableBody.innerHTML = '<tr><td colspan="2" class="phantom-table-empty">loading...</td></tr>';
}

function setPhantomTableError(msg) {
  phantomTableBody.innerHTML = '<tr><td colspan="2" class="phantom-table-empty">' + msg + '</td></tr>';
}

// --- Button handlers ---

document.getElementById('btnRefresh').addEventListener('click', function () {
  if (window.refreshPhantoms) {
    window.refreshPhantoms();
  }
});

btnUpload.addEventListener('click', function () {
  if (window.uploadPhantom) {
    window.uploadPhantom();
  }
});

// --- Expose to pipeline.js (ES module) ---

window.appendLog = appendLog;
window.clearLog = clearLog;
window.setOutputActive = setOutputActive;
window.renderPhantomTable = renderPhantomTable;
window.setPhantomTableLoading = setPhantomTableLoading;
window.setPhantomTableError = setPhantomTableError;
