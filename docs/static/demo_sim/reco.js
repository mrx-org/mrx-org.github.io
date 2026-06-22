// --- FFT helpers ---

function nextPow2(n) {
  var p = 1;
  while (p < n) p *= 2;
  return p;
}

function fft1d(re, im, inverse) {
  var N = re.length;
  for (var i = 1, j = 0; i < N; i++) {
    var bit = N >> 1;
    while (j & bit) { j ^= bit; bit >>= 1; }
    j ^= bit;
    if (i < j) {
      var tmp = re[i]; re[i] = re[j]; re[j] = tmp;
      tmp = im[i]; im[i] = im[j]; im[j] = tmp;
    }
  }
  var sign = inverse ? 1 : -1;
  for (var len = 2; len <= N; len *= 2) {
    var halfLen = len / 2;
    var angle = sign * 2 * Math.PI / len;
    var wRe = Math.cos(angle);
    var wIm = Math.sin(angle);
    for (var i = 0; i < N; i += len) {
      var curRe = 1, curIm = 0;
      for (var k = 0; k < halfLen; k++) {
        var evenIdx = i + k;
        var oddIdx = i + k + halfLen;
        var tRe = curRe * re[oddIdx] - curIm * im[oddIdx];
        var tIm = curRe * im[oddIdx] + curIm * re[oddIdx];
        re[oddIdx] = re[evenIdx] - tRe;
        im[oddIdx] = im[evenIdx] - tIm;
        re[evenIdx] += tRe;
        im[evenIdx] += tIm;
        var newCurRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = newCurRe;
      }
    }
  }
  if (inverse) {
    for (var i = 0; i < N; i++) { re[i] /= N; im[i] /= N; }
  }
}

function ifft2d(re, im, rows, cols) {
  var rowRe = new Float64Array(cols);
  var rowIm = new Float64Array(cols);
  for (var r = 0; r < rows; r++) {
    var off = r * cols;
    for (var c = 0; c < cols; c++) { rowRe[c] = re[off + c]; rowIm[c] = im[off + c]; }
    fft1d(rowRe, rowIm, true);
    for (var c = 0; c < cols; c++) { re[off + c] = rowRe[c]; im[off + c] = rowIm[c]; }
  }
  var colRe = new Float64Array(rows);
  var colIm = new Float64Array(rows);
  for (var c = 0; c < cols; c++) {
    for (var r = 0; r < rows; r++) { colRe[r] = re[r * cols + c]; colIm[r] = im[r * cols + c]; }
    fft1d(colRe, colIm, true);
    for (var r = 0; r < rows; r++) { re[r * cols + c] = colRe[r]; im[r * cols + c] = colIm[r]; }
  }
}

function fftshift2d(data, rows, cols) {
  var halfR = rows >> 1;
  var halfC = cols >> 1;
  for (var r = 0; r < halfR; r++) {
    for (var c = 0; c < cols; c++) {
      var i1 = r * cols + c;
      var r2 = r + halfR;
      var c2 = (c + halfC) % cols;
      var i2 = r2 * cols + c2;
      var tmp = data[i1]; data[i1] = data[i2]; data[i2] = tmp;
    }
  }
}

// --- Twilight cyclic colormap (256 entries, RGB 0-255) ---

var TWILIGHT = [
  [226,217,226],[225,217,226],[224,217,226],[222,217,225],[221,217,224],[220,217,223],[218,216,223],[216,216,222],
  [214,215,221],[212,214,220],[210,213,219],[208,212,217],[205,211,216],[203,210,215],[200,208,214],[197,207,213],
  [194,206,212],[191,204,211],[188,203,209],[185,201,208],[182,200,207],[179,198,206],[176,197,205],[173,195,205],
  [170,194,204],[167,192,203],[164,190,202],[161,189,201],[158,187,201],[156,185,200],[153,184,200],[150,182,199],
  [147,180,198],[145,178,198],[142,177,197],[140,175,197],[137,173,197],[135,171,196],[133,169,196],[130,167,195],
  [128,165,195],[126,164,195],[124,162,194],[122,160,194],[120,158,194],[118,156,193],[117,154,193],[115,152,193],
  [113,150,193],[112,148,192],[110,146,192],[109,144,192],[108,142,191],[107,140,191],[105,138,191],[104,136,190],
  [103,134,190],[102,132,189],[102,130,189],[101,127,189],[100,125,188],[99,123,188],[99,121,187],[98,119,187],
  [98,117,186],[97,114,186],[97,112,185],[96,110,184],[96,108,184],[96,105,183],[96,103,182],[95,101,181],
  [95,98,180],[95,96,180],[95,94,179],[95,91,178],[95,89,177],[95,87,176],[94,84,174],[94,82,173],[94,79,172],
  [94,77,171],[94,75,169],[94,72,168],[94,70,166],[94,67,165],[93,65,163],[93,62,161],[93,60,160],[93,58,158],
  [92,55,156],[92,53,154],[91,50,152],[91,48,149],[90,46,147],[90,43,144],[89,41,142],[88,39,139],[87,37,136],
  [87,35,133],[86,33,130],[85,31,127],[83,30,124],[82,28,121],[81,26,117],[79,25,114],[78,24,111],[76,23,107],
  [75,22,104],[73,21,100],[71,20,97],[70,20,94],[68,19,90],[66,18,87],[65,18,84],[63,18,81],[61,17,78],
  [60,17,75],[58,17,73],[57,17,70],[55,17,68],[54,17,66],[53,17,64],[52,17,62],[51,17,60],[50,18,58],
  [49,19,57],[48,20,55],[48,20,55],[49,19,55],[51,18,55],[52,18,56],[53,17,56],[54,17,57],[56,17,57],
  [58,17,58],[59,17,59],[61,17,60],[63,18,61],[65,18,61],[67,18,62],[70,18,64],[72,19,65],[74,19,66],
  [77,20,67],[79,20,68],[82,21,69],[84,21,70],[87,22,71],[89,22,72],[92,23,73],[95,23,74],[97,24,75],
  [100,25,75],[103,25,76],[105,26,77],[108,27,78],[111,28,78],[113,29,79],[116,30,79],[118,31,79],
  [121,32,80],[123,33,80],[126,34,80],[128,35,80],[131,37,80],[133,38,80],[135,39,80],[138,41,80],
  [140,42,80],[142,44,80],[144,46,80],[146,47,80],[148,49,80],[150,51,80],[152,53,80],[154,55,80],
  [156,57,80],[158,59,80],[160,61,80],[161,63,80],[163,65,80],[165,67,80],[166,69,80],[168,71,80],
  [169,73,80],[171,75,80],[172,77,81],[174,80,81],[175,82,81],[177,84,82],[178,86,82],[179,89,83],
  [181,91,83],[182,93,84],[183,95,85],[184,98,85],[185,100,86],[186,102,87],[187,105,88],[188,107,89],
  [189,110,90],[190,112,91],[191,114,93],[192,117,94],[193,119,95],[194,122,97],[194,124,99],[195,127,100],
  [196,129,102],[197,132,104],[197,134,106],[198,137,108],[198,139,110],[199,142,113],[200,144,115],
  [200,146,117],[201,149,120],[201,151,123],[202,154,125],[202,156,128],[203,159,131],[204,161,134],
  [204,163,137],[205,166,140],[205,168,143],[206,171,146],[207,173,150],[207,175,153],[208,178,156],
  [209,180,160],[209,182,163],[210,184,167],[211,186,170],[212,189,173],[213,191,177],[214,193,180],
  [215,195,184],[216,197,187],[216,199,190],[217,201,194],[218,203,197],[219,204,200],[220,206,203],
  [221,208,206],[221,209,209],[222,211,211],[223,212,214],[223,213,216],[224,214,218],[224,215,219],
  [225,216,221],[225,216,223],[226,217,224],[226,217,225]
];

// --- Regridding: (trajectory, signal) -> { kRe, kIm, kOrder, fillCount, Nx, Ny } ---

export function regrid(trajectory, signal) {
  var nSamples = signal.length;

  var kxVals = new Float64Array(nSamples);
  var kyVals = new Float64Array(nSamples);
  for (var i = 0; i < nSamples; i++) {
    kxVals[i] = trajectory[i][0];
    kyVals[i] = trajectory[i][1];
  }

  var EPS = 1e-6;
  function roundK(v) { return Math.round(v / EPS) * EPS; }

  var kxSet = new Map();
  var kySet = new Map();
  for (var i = 0; i < nSamples; i++) {
    var rkx = roundK(kxVals[i]);
    var rky = roundK(kyVals[i]);
    if (!kxSet.has(rkx)) kxSet.set(rkx, kxSet.size);
    if (!kySet.has(rky)) kySet.set(rky, kySet.size);
  }

  var uniqueKx = Array.from(kxSet.keys()).sort(function (a, b) { return a - b; });
  var uniqueKy = Array.from(kySet.keys()).sort(function (a, b) { return a - b; });

  var Nx = nextPow2(uniqueKx.length);
  var Ny = nextPow2(uniqueKy.length);

  var kxIndex = new Map();
  var kyIndex = new Map();
  var offX = (Nx - uniqueKx.length) >> 1;
  var offY = (Ny - uniqueKy.length) >> 1;
  for (var i = 0; i < uniqueKx.length; i++) kxIndex.set(roundK(uniqueKx[i]), i + offX);
  for (var i = 0; i < uniqueKy.length; i++) kyIndex.set(roundK(uniqueKy[i]), i + offY);

  var kRe = new Float64Array(Ny * Nx);
  var kIm = new Float64Array(Ny * Nx);
  var kOrder = new Float64Array(Ny * Nx);
  for (var i = 0; i < kOrder.length; i++) kOrder[i] = -1;
  var fillCount = 0;

  for (var i = 0; i < nSamples; i++) {
    var ix = kxIndex.get(roundK(kxVals[i]));
    var iy = kyIndex.get(roundK(kyVals[i]));
    if (ix !== undefined && iy !== undefined) {
      var idx = iy * Nx + ix;
      kRe[idx] = signal[i][0];
      kIm[idx] = signal[i][1];
      if (kOrder[idx] < 0) kOrder[idx] = fillCount++;
    }
  }

  return { kRe: kRe, kIm: kIm, kOrder: kOrder, fillCount: fillCount, Nx: Nx, Ny: Ny };
}

// --- FFT reconstruction: kspace -> { re, im, Nx, Ny } ---

export function fftReco(kRe, kIm, Nx, Ny) {
  // Copy so we don't mutate the input
  var re = new Float64Array(kRe);
  var im = new Float64Array(kIm);

  fftshift2d(re, Ny, Nx);
  fftshift2d(im, Ny, Nx);
  ifft2d(re, im, Ny, Nx);
  fftshift2d(re, Ny, Nx);
  fftshift2d(im, Ny, Nx);

  return { re: re, im: im, Nx: Nx, Ny: Ny };
}

// --- Plotting: complex image -> magnitude and phase ImageData ---

export function recoToImages(re, im, Nx, Ny) {
  var N = Ny * Nx;

  // Magnitude
  var mag = new Float64Array(N);
  var maxMag = 0;
  for (var i = 0; i < N; i++) {
    mag[i] = Math.sqrt(re[i] * re[i] + im[i] * im[i]);
    if (mag[i] > maxMag) maxMag = mag[i];
  }
  var magData = new ImageData(Nx, Ny);
  var md = magData.data;
  var scale = maxMag > 0 ? 255 / maxMag : 0;
  for (var i = 0; i < N; i++) {
    var v = Math.min(255, Math.round(mag[i] * scale));
    md[i * 4] = v; md[i * 4 + 1] = v; md[i * 4 + 2] = v; md[i * 4 + 3] = 255;
  }

  // Phase (twilight colormap)
  var phaseData = new ImageData(Nx, Ny);
  var pd = phaseData.data;
  var nTwilight = TWILIGHT.length;
  for (var i = 0; i < N; i++) {
    var phi = Math.atan2(im[i], re[i]);
    var t = (phi + Math.PI) / (2 * Math.PI);
    var ci = Math.min(nTwilight - 1, Math.floor(t * nTwilight));
    var c = TWILIGHT[ci];
    pd[i * 4] = c[0]; pd[i * 4 + 1] = c[1]; pd[i * 4 + 2] = c[2]; pd[i * 4 + 3] = 255;
  }

  return { magnitude: magData, phase: phaseData };
}

// --- Plotting: kspace data -> log magnitude and fill order ImageData ---

export function kspaceToImages(kRe, kIm, kOrder, fillCount, Nx, Ny) {
  var N = Ny * Nx;

  // Log-magnitude
  var kMag = new Float64Array(N);
  var maxKMag = 0;
  for (var i = 0; i < N; i++) {
    kMag[i] = Math.log1p(Math.sqrt(kRe[i] * kRe[i] + kIm[i] * kIm[i]));
    if (kMag[i] > maxKMag) maxKMag = kMag[i];
  }
  var logMagData = new ImageData(Nx, Ny);
  var ld = logMagData.data;
  var kScale = maxKMag > 0 ? 255 / maxKMag : 0;
  for (var i = 0; i < N; i++) {
    var v = Math.min(255, Math.round(kMag[i] * kScale));
    ld[i * 4] = v; ld[i * 4 + 1] = v; ld[i * 4 + 2] = v; ld[i * 4 + 3] = 255;
  }

  // Fill order
  var orderData = new ImageData(Nx, Ny);
  var od = orderData.data;
  var orderScale = fillCount > 1 ? 255 / (fillCount - 1) : 0;
  for (var i = 0; i < N; i++) {
    var v = kOrder[i] < 0 ? 0 : Math.round(kOrder[i] * orderScale);
    od[i * 4] = v; od[i * 4 + 1] = v; od[i * 4 + 2] = v; od[i * 4 + 3] = 255;
  }

  return { logMagnitude: logMagData, order: orderData };
}

