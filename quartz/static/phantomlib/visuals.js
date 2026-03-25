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
var phantomTable = document.getElementById('phantomTable');
var phantomPlaceholder = document.getElementById('phantomPlaceholder');
window.selectedPhantom = null;

var btnRetrieve = document.getElementById('btnRetrieve');
var retrieveLabel = document.getElementById('retrieveLabel');

function updateRetrieveState() {
  if (window.selectedPhantom) {
    btnRetrieve.disabled = false;
    retrieveLabel.textContent = window.selectedPhantom;
  } else {
    btnRetrieve.disabled = true;
    retrieveLabel.textContent = 'select phantom first';
  }
}

function selectPhantomRow(tr) {
  var prev = phantomTableBody.querySelector('tr.selected');
  if (prev) prev.classList.remove('selected');
  tr.classList.add('selected');
  window.selectedPhantom = tr.getAttribute('data-name');
  updateRetrieveState();
}

function showPhantomPlaceholder(text) {
  phantomPlaceholder.querySelector('h3').textContent = text;
  phantomPlaceholder.style.display = '';
  phantomTable.style.display = 'none';
}

function renderPhantomTable(entries) {
  phantomTableBody.innerHTML = '';
  window.selectedPhantom = null;
  updateRetrieveState();
  if (entries.length === 0) {
    showPhantomPlaceholder('NO DATA');
    return;
  }
  phantomPlaceholder.style.display = 'none';
  phantomTable.style.display = '';
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
  showPhantomPlaceholder('LOADING...');
}

function setPhantomTableError(msg) {
  showPhantomPlaceholder(msg.toUpperCase());
}

// --- Output result ---

var resultPlaceholder = document.getElementById('resultPlaceholder');
var resultTitle = document.getElementById('resultTitle');
var resultTable = document.getElementById('resultTable');
var resultTableBody = document.getElementById('resultTableBody');
var sliceControls = document.getElementById('sliceControls');
var sliceSlider = document.getElementById('sliceSlider');
var sliceValue = document.getElementById('sliceValue');
var tissueImages = document.getElementById('tissueImages');

// Stored phantom for re-rendering on slice change
var currentPhantom = null;
var currentTissueNames = null;
var currentNx = 0, currentNy = 0, currentNz = 0;

// --- Image helpers ---

function extractSlice(data3d, nx, ny, nz, sliceZ) {
  var slice = new Float64Array(nx * ny);
  for (var x = 0; x < nx; x++) {
    for (var y = 0; y < ny; y++) {
      slice[x * ny + y] = data3d[x * ny * nz + y * nz + sliceZ];
    }
  }
  return slice;
}

function generateImage(data, width, height) {
  var min = Infinity, max = -Infinity;
  for (var i = 0; i < data.length; i++) {
    if (data[i] < min) min = data[i];
    if (data[i] > max) max = data[i];
  }
  var range = max - min || 1;

  var canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  var ctx = canvas.getContext('2d');
  var imgData = ctx.createImageData(width, height);

  for (var y = 0; y < height; y++) {
    for (var x = 0; x < width; x++) {
      var srcIdx = x * height + y;
      var dstIdx = (x + (height - 1 - y) * width) * 4;
      var v = Math.round(((data[srcIdx] - min) / range) * 255);
      imgData.data[dstIdx] = v;
      imgData.data[dstIdx + 1] = v;
      imgData.data[dstIdx + 2] = v;
      imgData.data[dstIdx + 3] = 255;
    }
  }

  ctx.putImageData(imgData, 0, 0);
  return canvas;
}

function renderSlice(sliceZ) {
  tissueImages.innerHTML = '';
  var tissues = currentPhantom.tissues;

  for (var i = 0; i < currentTissueNames.length; i++) {
    var name = currentTissueNames[i];
    var tissue = tissues.get(name);

    // Render density and dB0
    var props = [['density', 'density'], ['db0', 'dB0']];
    for (var p = 0; p < props.length; p++) {
      var prop = props[p][0];
      var label = props[p][1];
      var vol = tissue[prop];
      var vNx = vol.shape[0], vNy = vol.shape[1], vNz = vol.shape[2];
      var isConst = (vNx === 1 && vNy === 1 && vNz === 1);

      var data;
      if (isConst) {
        data = new Float64Array(currentNx * currentNy).fill(vol.data.Float[0]);
      } else {
        data = extractSlice(vol.data.Float, vNx, vNy, vNz, Math.min(sliceZ, vNz - 1));
      }

      var canvas = generateImage(data, isConst ? currentNx : vNx, isConst ? currentNy : vNy);
      var cell = document.createElement('div');
      cell.className = 'tissue-cell';
      cell.appendChild(canvas);

      var labelEl = document.createElement('div');
      labelEl.className = 'tissue-cell-label';
      labelEl.textContent = name + ' ' + label;
      cell.appendChild(labelEl);

      tissueImages.appendChild(cell);
    }
  }
}

sliceSlider.addEventListener('input', function () {
  var z = parseInt(sliceSlider.value);
  sliceValue.textContent = z + ' / ' + (currentNz - 1);
  renderSlice(z);
});

// --- Render result ---

function renderResult(phantom) {
  currentPhantom = phantom;
  var tissues = phantom.tissues;
  currentTissueNames = Array.from(tissues.keys());
  var first = tissues.values().next().value;
  currentNx = first.density.shape[0];
  currentNy = first.density.shape[1];
  currentNz = first.density.shape[2];

  resultPlaceholder.style.display = 'none';
  resultTitle.style.display = '';
  resultTitle.textContent = currentTissueNames.length + ' TISSUE(S), ' + currentNx + ' x ' + currentNy + ' x ' + currentNz;

  // Tissue properties table
  resultTableBody.innerHTML = '';
  for (var i = 0; i < currentTissueNames.length; i++) {
    var name = currentTissueNames[i];
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

  // Slice slider
  var midZ = Math.floor(currentNz / 2);
  sliceSlider.max = currentNz - 1;
  sliceSlider.value = midZ;
  sliceValue.textContent = midZ + ' / ' + (currentNz - 1);
  sliceControls.style.display = '';

  // Render initial slice
  renderSlice(midZ);
}

function clearResult() {
  currentPhantom = null;
  currentTissueNames = null;
  resultPlaceholder.style.display = '';
  resultTitle.style.display = 'none';
  resultTable.style.display = 'none';
  resultTableBody.innerHTML = '';
  sliceControls.style.display = 'none';
  tissueImages.innerHTML = '';
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
