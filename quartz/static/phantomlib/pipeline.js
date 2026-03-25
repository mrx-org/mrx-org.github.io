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
  var file = document.getElementById('archiveFile').files[0];
  if (!file) return;

  btn.disabled = true;
  window.clearLog();
  window.setOutputActive(true);

  try {
    await ensureWasm();

    var sizeMB = (file.size / 1048576).toFixed(1);
    window.appendLog('Reading "' + file.name + '" (' + sizeMB + ' MB)...\n');
    var arrayBuf = await file.arrayBuffer();
    var bytes = new Uint8Array(arrayBuf);

    window.appendLog('Uploading to ' + PHANTOMLIB_ADDR + ' ...\n');
    var t0 = performance.now();

    var result = await call(
      PHANTOMLIB_ADDR,
      {
        Dict: {
          mode: { Str: 'store' },
          archive_name: { Str: file.name },
          data: { Bytes: bytes }
        }
      },
      function (msg) {
        window.appendLog('> ' + msg + '\n');
        return true;
      }
    );

    var elapsed = ((performance.now() - t0) / 1000).toFixed(1);
    window.appendLog('Upload completed in ' + elapsed + 's\n');
    window.appendLog(JSON.stringify(result, null, 2) + '\n');

    // Refresh the phantom list after successful upload
    await refreshPhantoms();
  } catch (err) {
    window.appendLog('ERROR: ' + err + '\n');
  } finally {
    window.setOutputActive(false);
    btn.disabled = false;
  }
}

// --- Expose to visuals.js ---

window.refreshPhantoms = refreshPhantoms;
window.uploadPhantom = uploadPhantom;
