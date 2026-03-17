import init, { call } from 'https://esm.sh/toolapi-wasm@0.4.5/toolapi_wasm.js';
import { regrid, fftReco, recoToImages, kspaceToImages } from './reco.js';

// --- Tool addresses ---

var CONSEQ_ADDR = 'wss://tool-conseq.fly.dev/tool';
var PHANTOMLIB_ADDR = 'wss://tool-phantomlib-flyio.fly.dev/tool';
var MR0SIM_ADDR = 'wss://tool-mr0sim.fly.dev/tool';
var RAPISIM_ADDR = 'wss://tool-rapisim.fly.dev/tool';
var SPINSIM_ADDR = 'wss://tool-spinsim.fly.dev/tool';
var TRAJEX_ADDR = 'wss://tool-trajex.fly.dev/tool';

var SIM_ADDRS = {
  rapisim: RAPISIM_ADDR,
  mr0sim: MR0SIM_ADDR,
  spinsim: SPINSIM_ADDR
};

// --- Phantom parameters (same as index.html) ---

function buildPhantomInput() {
  return {
    Dict: {
      subject: { Int: 4 },
      res_x: { Int: 72 },
      res_y: { Int: 87 },
      res_z: { Int: 1 },
      affine: {
        List: [
          { List: [{ Float: 2.5 }, { Float: 0.0 }, { Float: 0.0 }, { Float: -90.0 }] },
          { List: [{ Float: 0.0 }, { Float: 2.5 }, { Float: 0.0 }, { Float: -108.75 }] },
          { List: [{ Float: 0.0 }, { Float: 0.0 }, { Float: 2.5 }, { Float: -1.25 }] }
        ]
      }
    }
  };
}

// --- Timer helper ---

function startTimer(toolId) {
  var t0 = performance.now();
  var interval = setInterval(function () {
    var elapsed = ((performance.now() - t0) / 1000).toFixed(1);
    window.setToolTiming(toolId, elapsed);
  }, 100);
  return { t0: t0, interval: interval };
}

function stopTimer(timer, toolId) {
  clearInterval(timer.interval);
  var elapsed = ((performance.now() - timer.t0) / 1000).toFixed(1);
  window.setToolTiming(toolId, elapsed);
  return elapsed;
}

// --- Run a single tool ---

async function runTool(toolId, addr, input) {
  window.setToolActive(toolId, true);
  var timer = startTimer(toolId);

  try {
    var result = await call(addr, input, function (msg) {
      window.appendToolLog(toolId, '> ' + msg + '\n');
      return true;
    });

    var elapsed = stopTimer(timer, toolId);
    window.appendToolLog(toolId, 'done (' + elapsed + ' s)\n');
    window.setToolActive(toolId, false);
    return result;
  } catch (err) {
    stopTimer(timer, toolId);
    window.appendToolLog(toolId, 'ERROR: ' + err + '\n');
    window.setToolActive(toolId, false);
    throw err;
  }
}

// --- WASM init ---

var wasmReady = false;

// --- Pipeline ---

async function runPipeline() {
  var btn = document.getElementById('btnRun');
  btn.disabled = true;

  try {
    // Init WASM once
    if (!wasmReady) {
      await init();
      wasmReady = true;
    }

    var seqContent = window.seqContent;
    if (!seqContent) {
      console.error('No .seq file loaded');
      btn.disabled = false;
      return;
    }

    // Clear previous state
    window.clearPipeline();

    // ---- Phase 1: conseq + phantomlib in parallel ----

    var [conseqResult, phantomResult] = await Promise.all([
      runTool('conseq', CONSEQ_ADDR, {
        Dict: {
          seq_file: { Str: seqContent },
          exact_trajectory: { Bool: false }
        }
      }),
      runTool('phantomlib', PHANTOMLIB_ADDR, buildPhantomInput())
    ]);

    var events = conseqResult.TypedList.InstantSeqEvent;
    var gmTissue = phantomResult.SegmentedPhantom.tissues.get('gm');
    var gmT1 = gmTissue.t1;
    var gmT2 = gmTissue.t2;

    console.log('Phase 1 complete:', events.length, 'events, gm t1=' + gmT1 + ' t2=' + gmT2);

    // ---- Phase 2: simtool + trajex in parallel ----

    var [simResult, trajexResult] = await Promise.all([
      runTool('simtool', SIM_ADDRS[window.simTool] || RAPISIM_ADDR, {
        Dict: {
          sequence: { TypedList: { InstantSeqEvent: events } },
          phantom: phantomResult,
          spins_per_voxel: { Int: 10 }
        }
      }),
      runTool('trajex', TRAJEX_ADDR, {
        Dict: {
          sequence: { TypedList: { InstantSeqEvent: events } },
          t1: { Float: gmT1 },
          t2: { Float: gmT2 },
          min_mag: { Float: 0.001 }
        }
      })
    ]);

    // HACK: needed because mr0sim currently does not return a TypedList (like it should, toolapi-py error)
    var signal = null;
    try {
      signal = simResult.List.map((x) => x.Complex);
    } catch {
      signal = simResult.TypedList.Complex;
    }
    var trajectory = trajexResult.TypedList.Vec4;

    console.log('Phase 2 complete:', signal.length, 'signal samples,', trajectory.length, 'trajectory points');

    // ---- Phase 3: local reconstruction ----

    var grid = regrid(trajectory, signal);
    var kImages = kspaceToImages(grid.kRe, grid.kIm, grid.kOrder, grid.fillCount, grid.Nx, grid.Ny);
    var reco = fftReco(grid.kRe, grid.kIm, grid.Nx, grid.Ny);
    var recoImages = recoToImages(reco.re, reco.im, reco.Nx, reco.Ny);

    console.log('Reconstruction complete:', grid.Nx, 'x', grid.Ny);

    // Render output
    window.renderOutput(signal, {
      imageData: recoImages.magnitude,
      phaseData: recoImages.phase,
      kspaceData: kImages.logMagnitude,
      kOrderData: kImages.order,
      Nx: grid.Nx,
      Ny: grid.Ny
    });

  } catch (err) {
    console.error('Pipeline error:', err);
  } finally {
    btn.disabled = false;
  }
}

// --- Expose to visuals.js ---

window.runPipeline = runPipeline;
