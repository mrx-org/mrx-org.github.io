// --- Tool addresses ---

var PHANTOMLIB_ADDR = 'wss://tool-phantomlib-flyio.fly.dev/tool';

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

    // TODO: implement upload via toolapi-wasm
    console.log('Upload:', file.name, '(' + file.size + ' bytes)');

  } catch (err) {
    console.error('Upload error:', err);
  } finally {
    btn.disabled = false;
  }
}

// --- Expose to visuals.js ---

window.uploadPhantom = uploadPhantom;
