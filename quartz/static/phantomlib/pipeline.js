import init, { call } from 'https://unpkg.com/toolapi@0.5.2/toolapi.js';

// --- Tool addresses ---

var PHANTOMLIB_ADDR = 'wss://tool-phantomlib.fly.dev/tool';

// --- WASM init ---

var wasmReady = false;

async function ensureWasm() {
  if (!wasmReady) {
    await init();
    wasmReady = true;
  }
}

// --- Refresh phantom list ---

async function refreshPhantoms() {
  window.clearLog();
  window.setOutputActive(true);
  window.setPhantomTableLoading();
  window.appendLog('Connecting to ' + PHANTOMLIB_ADDR + ' ...\n');

  try {
    await ensureWasm();
    window.appendLog('Requesting phantom list...\n');

    var result = await call(
      PHANTOMLIB_ADDR,
      { Dict: { mode: { Str: 'list' } } },
      function (msg) {
        window.appendLog('> ' + msg + '\n');
        return true;
      }
    );

    var phantoms = result.TypedDict.Str;
    var entries = [];
    phantoms.forEach(function (dateStr, name) {
      entries.push([name, dateStr]);
    });
    entries.sort(function (a, b) {
      return new Date(b[1]) - new Date(a[1]);
    });

    window.appendLog('Found ' + entries.length + ' phantom(s)\n');
    window.renderPhantomTable(entries);
  } catch (err) {
    window.appendLog('ERROR: ' + err + '\n');
    window.setPhantomTableError('error loading phantoms');
  } finally {
    window.setOutputActive(false);
  }
}

// --- Upload handler ---

async function uploadPhantom() {
  var btn = document.getElementById('btnUpload');
  btn.disabled = true;

  try {
    var file = document.getElementById('archiveFile').files[0];
    if (!file) {
      btn.disabled = false;
      return;
    }

    // TODO: implement upload via toolapi
    console.log('Upload:', file.name, '(' + file.size + ' bytes)');

  } catch (err) {
    console.error('Upload error:', err);
  } finally {
    btn.disabled = false;
  }
}

// --- Expose to visuals.js ---

window.refreshPhantoms = refreshPhantoms;
window.uploadPhantom = uploadPhantom;
