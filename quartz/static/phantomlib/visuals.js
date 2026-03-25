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
window.selectedPhantom = null;

var btnRetrieve = document.getElementById('btnRetrieve');
var retrieveLabel = document.getElementById('retrieveLabel');

function updateRetrieveState() {
  if (window.selectedPhantom) {
    btnRetrieve.disabled = false;
    retrieveLabel.textContent = window.selectedPhantom;
  } else {
    btnRetrieve.disabled = true;
    retrieveLabel.textContent = 'select a phantom first';
  }
}

function selectPhantomRow(tr) {
  var prev = phantomTableBody.querySelector('tr.selected');
  if (prev) prev.classList.remove('selected');
  tr.classList.add('selected');
  window.selectedPhantom = tr.getAttribute('data-name');
  updateRetrieveState();
}

function renderPhantomTable(entries) {
  phantomTableBody.innerHTML = '';
  window.selectedPhantom = null;
  updateRetrieveState();
  if (entries.length === 0) {
    var tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="2" class="phantom-table-empty">no phantoms found</td>';
    phantomTableBody.appendChild(tr);
    return;
  }
  for (var i = 0; i < entries.length; i++) {
    var tr = document.createElement('tr');
    tr.setAttribute('data-name', entries[i][0]);
    var tdName = document.createElement('td');
    tdName.textContent = entries[i][0];
    var tdDate = document.createElement('td');
    tdDate.textContent = entries[i][1];
    tr.appendChild(tdName);
    tr.appendChild(tdDate);
    tr.addEventListener('click', function () {
      selectPhantomRow(this);
    });
    phantomTableBody.appendChild(tr);
  }
  // Select first entry by default
  selectPhantomRow(phantomTableBody.querySelector('tr'));
}

function setPhantomTableLoading() {
  phantomTableBody.innerHTML = '<tr><td colspan="2" class="phantom-table-empty">loading...</td></tr>';
}

function setPhantomTableError(msg) {
  phantomTableBody.innerHTML = '<tr><td colspan="2" class="phantom-table-empty">' + msg + '</td></tr>';
}

// --- Output result ---

var outputTitle = document.getElementById('resultTitle');
var resultTable = document.getElementById('resultTable');
var resultTableBody = document.getElementById('resultTableBody');

function renderResult(phantom) {
  var tissues = phantom.tissues;
  var tissueNames = Array.from(tissues.keys());
  var first = tissues.values().next().value;
  var nx = first.density.shape[0];
  var ny = first.density.shape[1];
  var nz = first.density.shape[2];

  outputTitle.textContent = tissueNames.length + ' TISSUE(S), ' + nx + ' x ' + ny + ' x ' + nz;

  resultTableBody.innerHTML = '';
  for (var i = 0; i < tissueNames.length; i++) {
    var name = tissueNames[i];
    var t = tissues.get(name);
    var tr = document.createElement('tr');
    var tdName = document.createElement('td');
    tdName.textContent = name;
    tr.appendChild(tdName);
    var keys = ['adc', 't1', 't2', 't2dash'];
    for (var k = 0; k < keys.length; k++) {
      var td = document.createElement('td');
      td.textContent = t[keys[k]].toFixed(4);
      tr.appendChild(td);
    }
    resultTableBody.appendChild(tr);
  }
  resultTable.style.display = '';
}

function clearResult() {
  outputTitle.textContent = 'NO DATA';
  resultTable.style.display = 'none';
  resultTableBody.innerHTML = '';
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

btnRetrieve.addEventListener('click', function () {
  if (window.retrievePhantom) {
    window.retrievePhantom();
  }
});

// --- Expose to pipeline.js (ES module) ---

window.appendLog = appendLog;
window.clearLog = clearLog;
window.setOutputActive = setOutputActive;
window.renderPhantomTable = renderPhantomTable;
window.setPhantomTableLoading = setPhantomTableLoading;
window.setPhantomTableError = setPhantomTableError;
window.renderResult = renderResult;
window.clearResult = clearResult;
