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

// --- Button handlers ---

document.getElementById('btnRefresh').addEventListener('click', function () {
  // TODO: implement refresh
});

btnUpload.addEventListener('click', function () {
  if (window.uploadPhantom) {
    window.uploadPhantom();
  }
});
