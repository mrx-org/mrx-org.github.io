## View sum of 4D segments


## allow prot_ files in seq_explorer, check why my bultin prot function are not found 


### 0. Fix Local Development (Immediate)
- **Problem:** `seq_explorer.js` caches `fetch` requests for local/built-in files, preventing edits (like adding `prot_`) from appearing.
- **Fix:** Add `?t=${Date.now()}` cache-busting to `fetch` calls in `loadLocalFile` and parameter extraction logic.
- **UI:** Update `seq_explorer.js` filter to explicitly include `prot_` prefix (e.g., "Only seq_/prot_ or main") so protocols appear without unchecking the filter.

### 1. Protocol Format & Discovery
**Goal:** Protocols (`prot_*`) act as first-class citizens alongside Sequences (`seq_*`).

- **Discovery:** 
  - Ensure `SourceManager` parses `prot_*` functions.
  - Update `renderTree` in `seq_explorer.js` to group/sort `prot_` functions effectively (possibly above or below `seq_`).
- **Parameter Extraction:** 
  - Use existing `inspect`/AST logic on `prot_*` functions. 
  - **Convention:** The `prot_` function signature *is* the source of truth for defaults. (No complex body parsing needed for the `prot_...(**kwargs)` wrapper pattern).

### 2. Run History (Temp Protocols)
**Goal:** Every scan saves a reproducible protocol file.

- **Generation (Scan Time):**
  - When `SCAN` is clicked, capture the resolved parameters.
  - Generate a small Python string:
    ```python
    from original_file import seq_Function
    def prot_scan_001_Timestamp(**kwargs):
        # ... defaults from this run ...
        return seq_Function(**kwargs)
    ```
- **Storage:**
  - Write this file to Pyodide VFS (e.g., `/user_protocols/scan_001.py`).
- **Integration:**
  - Auto-register `/user_protocols` as a dynamic Source in `SequenceExplorer`.
  - New scans appear immediately in the file tree under "Run History" or similar.

### 3. Job Metadata
- Update `ScanModule` to link the resulting NIfTI job to this generated protocol file path.
- Enable "Replay" by loading that protocol file from the job list.
