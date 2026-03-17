window.seqContent = '';

// --- Theme colors (loaded from CSS) ---

var rootStyle = getComputedStyle(document.documentElement);
var COLOR_SHADOW_DARK = rootStyle.getPropertyValue('--shadow-dark').trim();
var COLOR_SHADOW_LIGHT = rootStyle.getPropertyValue('--shadow-light').trim();
var COLOR_ACCENT = rootStyle.getPropertyValue('--accent').trim();

function complementaryColor(hex) {
  var r = parseInt(hex.slice(1, 3), 16);
  var g = parseInt(hex.slice(3, 5), 16);
  var b = parseInt(hex.slice(5, 7), 16);
  return '#' + (255 - r).toString(16).padStart(2, '0') +
               (255 - g).toString(16).padStart(2, '0') +
               (255 - b).toString(16).padStart(2, '0');
}
var COLOR_ACCENT_COMP = complementaryColor(COLOR_ACCENT);

// --- Tool logs ---

var toolLogs = {
  conseq: '',
  phantomlib: '',
  simtool: '',
  trajex: ''
};

var activeViewer = null; // null, 'file', or a tool id

var overlay = document.getElementById('viewerOverlay');
var viewerContent = document.getElementById('viewerContent');
var viewerSubtitle = document.getElementById('viewerSubtitle');

// --- Tool log helpers ---

function last3Lines(text) {
  if (!text) return '';
  var lines = text.trimEnd().split('\n');
  return lines.slice(-3).join('\n');
}

function updateConsole(toolId) {
  var el = document.getElementById('console-' + toolId);
  if (el) el.textContent = last3Lines(toolLogs[toolId]);
}

function appendToolLog(toolId, text) {
  toolLogs[toolId] += text;
  updateConsole(toolId);
  if (activeViewer === toolId) {
    viewerContent.textContent = toolLogs[toolId];
  }
}

function clearPipeline() {
  for (var id in toolLogs) {
    toolLogs[id] = '';
    updateConsole(id);
    setToolActive(id, false);
    setToolTiming(id, '0.0');
  }
  if (activeViewer && activeViewer !== 'file') {
    viewerContent.textContent = '';
  }
}

// --- Pipeline card state ---

function setToolActive(toolId, active) {
  var card = document.querySelector('.pipeline-card[data-tool="' + toolId + '"]');
  if (card) {
    if (active) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }
  }
}

function setToolTiming(toolId, seconds) {
  var el = document.getElementById('timing-' + toolId);
  if (el) el.textContent = seconds + ' s';
}

// Initialize small consoles
for (var id in toolLogs) {
  updateConsole(id);
}

// --- Viewer ---

function openViewer(source, subtitle) {
  activeViewer = source;
  viewerSubtitle.textContent = subtitle;
  if (source === 'file') {
    viewerContent.textContent = window.seqContent;
  } else {
    viewerContent.textContent = toolLogs[source] || '';
  }
  overlay.classList.add('visible');
}

function closeViewer() {
  activeViewer = null;
  overlay.classList.remove('visible');
}

// --- File picker ---

document.getElementById('seqFile').addEventListener('change', function () {
  var label = document.getElementById('fileLabel');
  var btnRun = document.getElementById('btnRun');
  var btnView = document.getElementById('btnView');

  if (this.files.length > 0) {
    var file = this.files[0];
    var sizeKB = (file.size / 1024).toFixed(0);
    label.textContent = file.name + ' \u2013 ' + sizeKB + ' KB';

    var reader = new FileReader();
    reader.onload = function (e) {
      window.seqContent = e.target.result;
      btnRun.disabled = false;
      btnView.disabled = false;
    };
    reader.readAsText(file);
  } else {
    window.seqContent = '';
    label.textContent = 'no file selected';
    btnRun.disabled = true;
    btnView.disabled = true;
  }
});

// --- Simulator selector ---

var SIM_TOOLS = {
  rapisim: { title: 'RAPISIM', tagsId: 'tagsRapisim' },
  mr0sim:  { title: 'MR0SIM',  tagsId: 'tagsMr0sim' },
  spinsim: { title: 'SPINSIM', tagsId: 'tagsSpinsim' }
};

window.simTool = 'rapisim';
var simSelect = document.getElementById('simSelect');
var pageTitle = document.getElementById('pageTitle');
var simToolTitle = document.getElementById('simToolTitle');
var spinsWell = document.getElementById('spinsWell');

function updateSimSelection() {
  var info = SIM_TOOLS[window.simTool];
  pageTitle.textContent = info.title;
  simToolTitle.textContent = info.title;
  for (var key in SIM_TOOLS) {
    var el = document.getElementById(SIM_TOOLS[key].tagsId);
    if (el) el.style.display = key === window.simTool ? '' : 'none';
  }
  spinsWell.style.display = window.simTool === 'spinsim' ? '' : 'none';
}
updateSimSelection();

simSelect.addEventListener('change', function () {
  window.simTool = simSelect.value;
  updateSimSelection();
});

// --- Button handlers ---

document.getElementById('btnView').addEventListener('click', function () {
  openViewer('file', document.getElementById('fileLabel').textContent);
});

document.getElementById('btnRun').addEventListener('click', function () {
  if (window.runPipeline) {
    window.runPipeline();
  }
});

document.getElementById('viewerClose').addEventListener('click', closeViewer);

overlay.addEventListener('click', function (e) {
  if (e.target === overlay) closeViewer();
});

// --- Pipeline console click -> open viewer ---

document.querySelectorAll('.pipeline-card[data-tool] .console').forEach(function (el) {
  el.addEventListener('click', function () {
    var toolId = el.closest('.pipeline-card').getAttribute('data-tool');
    openViewer(toolId, toolId.toUpperCase());
  });
});

// --- Signal plot ---

function drawSignalPlot(canvasId, signal) {
  var canvas = document.getElementById(canvasId);
  var dpr = window.devicePixelRatio || 1;
  var rect = canvas.getBoundingClientRect();
  var W = rect.width;
  var H = rect.height;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  var ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  var N = signal.length;
  if (N === 0) return;

  var re = new Float64Array(N);
  var im = new Float64Array(N);
  for (var i = 0; i < N; i++) {
    re[i] = signal[i][0];
    im[i] = signal[i][1];
  }

  var vMin = Infinity, vMax = -Infinity;
  for (var i = 0; i < N; i++) {
    if (re[i] < vMin) vMin = re[i];
    if (re[i] > vMax) vMax = re[i];
    if (im[i] < vMin) vMin = im[i];
    if (im[i] > vMax) vMax = im[i];
  }
  var range = vMax - vMin || 1;
  vMin -= range * 0.05;
  vMax += range * 0.05;
  range = vMax - vMin;

  var pad = { l: 0, r: 0, t: 4, b: 4 };
  var plotW = W - pad.l - pad.r;
  var plotH = H - pad.t - pad.b;

  function toX(i) { return pad.l + (i / (N - 1)) * plotW; }
  function toY(v) { return pad.t + (1 - (v - vMin) / range) * plotH; }

  ctx.fillStyle = COLOR_SHADOW_DARK;
  ctx.fillRect(0, 0, W, H);

  // Zero line
  if (vMin < 0 && vMax > 0) {
    ctx.strokeStyle = COLOR_SHADOW_LIGHT;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.l, toY(0));
    ctx.lineTo(W - pad.r, toY(0));
    ctx.stroke();
  }

  function drawLine(data, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (var i = 1; i < N; i++) {
      ctx.lineTo(toX(i), toY(data[i]));
    }
    ctx.stroke();
  }

  drawLine(re, COLOR_ACCENT_COMP);
  drawLine(im, COLOR_ACCENT);
}

// --- Output rendering ---

function renderOutput(signal, recon) {
  var output = document.getElementById('outputContent');

  output.innerHTML =
    // 1. Signal
    '<div class="inset-card">' +
      '<h3>SIGNAL</h3>' +
      '<div class="signal-plot-wrap">' +
        '<canvas id="signalCanvas"></canvas>' +
        '<div class="signal-legend">' +
          '<span class="signal-legend-item"><span class="signal-legend-swatch" style="background:' + COLOR_ACCENT_COMP + ';"></span>real</span>' +
          '<span class="signal-legend-item"><span class="signal-legend-swatch" style="background:' + COLOR_ACCENT + ';"></span>imag</span>' +
        '</div>' +
      '</div>' +
    '</div>' +
    // 2. K-space
    '<div class="inset-card">' +
      '<h3>K-SPACE (REGRIDDED)</h3>' +
      '<div class="output-grid">' +
        '<div class="output-panel"><div class="output-label">LOG MAGNITUDE</div><img id="kspaceImg"></div>' +
        '<div class="output-panel"><div class="output-label">ORDER</div><img id="kOrderImg"></div>' +
      '</div>' +
    '</div>' +
    // 3. Reco
    '<div class="inset-card">' +
      '<h3>RECO (FFT)</h3>' +
      '<div class="output-grid">' +
        '<div class="output-panel"><div class="output-label">MAGNITUDE</div><img id="reconImg"></div>' +
        '<div class="output-panel"><div class="output-label">PHASE</div><img id="phaseImg"></div>' +
      '</div>' +
    '</div>';

  drawSignalPlot('signalCanvas', signal);

  function putImage(id, imgData, w, h) {
    var canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    canvas.getContext('2d').putImageData(imgData, 0, 0);
    document.getElementById(id).src = canvas.toDataURL('image/png');
  }

  putImage('kspaceImg', recon.kspaceData, recon.Nx, recon.Ny);
  putImage('kOrderImg', recon.kOrderData, recon.Nx, recon.Ny);
  putImage('reconImg', recon.imageData, recon.Nx, recon.Ny);
  putImage('phaseImg', recon.phaseData, recon.Nx, recon.Ny);
}

// --- Expose to pipeline.js (ES module) ---

window.appendToolLog = appendToolLog;
window.clearPipeline = clearPipeline;
window.setToolActive = setToolActive;
window.setToolTiming = setToolTiming;
window.renderOutput = renderOutput;
