"""The scanner-side script: runs on the PC next to a scanner, takes the sequences
queued for it from the gateway, has the Pulseq interpreter measure them and
uploads what it measured. See `docs/scan/design.md` in the mcp-gateway repo for
why it works this way.

This file lives only here, next to the session page on mrx-org.github.io
(`docs/scanner/`), which hands it out with a session's secrets filled in. The
gateway keeps its own copy of `adc_sample_counts` (`scan/seq.py`) - change both
together. It runs on whatever Python
that PC has. So it is one file, needs nothing but numpy
(which a standard Python or conda install on Windows comes with) and stays
Python 3.8 compatible: no `requests`, no `match`, no `X | Y` annotations.

Everything that runs lives behind functions, so that it can be imported to test.
"""

import argparse
import hashlib
import io
import json
import os
import random
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import warnings
from datetime import datetime
from typing import Callable, List, Optional

import numpy as np

# Filled in by the session page when it hands out the script (`scanner.render_script`):
# the session this copy belongs to. The runner secret is this script's only
# credential and is never shown; the scan token is what the operator shares.
BASE_URL = "__MRX_BASE_URL__"
RUNNER_SECRET = "__MRX_RUNNER_SECRET__"
SCAN_TOKEN = "__MRX_SCAN_TOKEN__"
OPERATOR = "__MRX_OPERATOR__"
# Siemens scanners do not follow MRX's physical sign convention, so the signal
# is complex conjugated before upload unless the session page said "no" (a
# copy that was not filled in conjugates too).
CONJUGATE = "__MRX_CONJUGATE__" != "no"

# The defaults for the site this was built for; every one can be overridden
DEFAULT_MEASUREMENT_DIR = r"W:\neuroradiologie\zaiss-mrx\measurement"
DEFAULT_SCANNER_MEASUREMENT_DIR = "C:/ProgramData/Siemens/Numaris/MriCustomer/CustomerSeq/pulseq/seq-files/measurement/"
DEFAULT_CONTROL_FILE = r"W:\neuroradiologie\zaiss-mrx\control\control.txt"
DEFAULT_COILS = 20
DEFAULT_ADC_PADDING = 4

# How often an idle script asks for work. Every request is also the heartbeat
# the gateway uses to tell whether the scanner is online (30 s), so this has to
# stay well below that.
POLL_INTERVAL = 3.0  # seconds
# Network failures are retried, waiting twice as long each time up to this
MAX_BACKOFF = 60.0  # seconds
# The interpreter's control file: a list of .seq paths that ends in this keyword
WAIT = "wait"
STATE_FILE = ".mrx_scanner_state.json"

# =============================================================================
# Pulseq: how long every ADC event is
# =============================================================================
# The `.seq.dat` has no header, so the only way to know where one readout ends
# and the next begins is the sequence that was measured. Reading the ADC events
# rather than `Nread`-style definitions means any sequence works, including ones
# whose ADCs differ in length (DREAM).

# Columns, counted from 1 as the Pulseq spec does. The ADC id is the 7th column
# of a block in every version since 1.2, and `num` the 2nd of an ADC event.
_BLOCK_ADC_COLUMN = 7
_ADC_NUM_COLUMN = 2


def adc_sample_counts(seq_text: str) -> List[int]:
    """`num_samples` of every ADC event, in the order the blocks play them."""
    sections = {}  # type: dict
    current = None
    for raw in seq_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            current = line.upper()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line.split())

    adc_nums = {}
    for cols in sections.get("[ADC]", []):
        adc_nums[int(cols[0])] = int(cols[_ADC_NUM_COLUMN - 1])

    counts = []
    for cols in sections.get("[BLOCKS]", []):
        if len(cols) < _BLOCK_ADC_COLUMN:
            raise ValueError("block line has too few columns: " + " ".join(cols))
        adc_id = int(cols[_BLOCK_ADC_COLUMN - 1])
        if adc_id == 0:
            continue
        if adc_id not in adc_nums:
            raise ValueError("block {} uses ADC {}, which is not defined".format(cols[0], adc_id))
        counts.append(adc_nums[adc_id])
    return counts


# =============================================================================
# `.seq.dat` -> `signal.npy`
# =============================================================================
# The interpreter writes one `<re> <im>` line per sample, nested ADC -> coil ->
# sample, with `padding` samples nobody understands at the end of every coil's
# readout (see `scan-plan/dat-format.md`). What `scan` hands out is the same
# signal as `(ADC samples, coils)`: row k is sample k of every coil.


def expected_lines(adc_counts: List[int], coils: int, padding: int) -> int:
    return coils * sum(n + padding for n in adc_counts)


def numpy_too_old_for_fast_loadtxt(version: Optional[str] = None) -> bool:
    """Whether numpy (or `version`) is older than 1.23, the first with a fast
    `np.loadtxt`, which `read_dat` relies on for large files."""
    m = re.match(r"(\d+)\.(\d+)", version or np.__version__)
    return m is not None and (int(m.group(1)), int(m.group(2))) < (1, 23)


def read_dat(dat) -> np.ndarray:
    """Every `<re> <im>` line of a `.seq.dat` (a path or an open text file) as
    one flat complex64 array, in file order. `np.loadtxt` parses straight into
    float32, so a large file costs about its signal's size in memory rather
    than the several times that splitting its text does. Raises `ValueError` if
    a line is not two numbers."""
    try:
        with warnings.catch_warnings():
            # An empty file is no different from one cut short: `convert` says so
            warnings.simplefilter("ignore", UserWarning)
            values = np.loadtxt(dat, dtype=np.float32, ndmin=2)
    except ValueError as e:
        # Without numpy's advice to use `usecols`, which is not ours to take
        raise ValueError("every line of the .seq.dat must be '<re> <im>': {}".format(str(e).split(";")[0]))
    if values.size == 0:
        return np.zeros(0, dtype="<c8")
    if values.shape[1] != 2:
        raise ValueError("every line of the .seq.dat must be '<re> <im>', these have {} values".format(values.shape[1]))
    return np.ascontiguousarray(values, dtype="<f4").view("<c8").ravel()


def convert(samples: np.ndarray, adc_counts: List[int], coils: int, padding: int) -> np.ndarray:
    """The samples from `read_dat` as complex64 of shape `(ADC samples, coils)`.
    Raises `ValueError` if they do not have the layout the arguments describe -
    the usual cause is a wrong `--coils` or `--adc-padding`, or a file that was
    cut short."""
    expected = expected_lines(adc_counts, coils, padding)
    if len(samples) != expected:
        raise ValueError(
            "the .seq.dat has {} lines, but {} coils x (ADC samples + {} padding) "
            "for this sequence make {} - check --coils and --adc-padding".format(
                len(samples), coils, padding, expected
            )
        )

    parts, offset = [], 0
    for n in adc_counts:
        # One ADC is `coils` readouts of `n + padding` samples in a row; its
        # transpose without the padding is `n` rows of the output.
        block = samples[offset : offset + coils * (n + padding)].reshape(coils, n + padding)
        parts.append(block[:, :n].T)
        offset += coils * (n + padding)
    if not parts:
        return np.zeros((0, coils), dtype="<c8")
    return np.concatenate(parts).astype("<c8", copy=False)


def npy_bytes(signal: np.ndarray) -> bytes:
    """`signal` from `convert` as the contents of a `.npy` file."""
    out = io.BytesIO()
    np.save(out, signal, allow_pickle=False)
    return out.getvalue()


def fake_dat(adc_counts: List[int], coils: int, padding: int, rng: "random.Random" = None) -> str:
    """Noise in the interpreter's layout, which is what `--simulate` writes in
    place of a measurement - so the conversion above runs on it too."""
    rng = rng or random.Random()
    lines = []
    for _ in range(expected_lines(adc_counts, coils, padding)):
        lines.append("{:.6f} {:.6f}".format(rng.gauss(0, 1), rng.gauss(0, 1)))
    return "\n".join(lines) + "\n"


# =============================================================================
# The control file and the measurement folder
# =============================================================================
# The Pulseq interpreter loops over `control.txt`: a list of `.seq` paths, as
# the scanner sees them, ending in `wait`. It remembers how far it got and runs
# whatever is appended, so a new sequence is measured by putting its line in
# front of the `wait`. Earlier lines are never touched - the interpreter counts
# them - and the operator may edit the file by hand, so it is read fresh every
# time rather than kept.


def scanner_path(scanner_dir: str, date: str, file_name: str) -> str:
    """A file in the dated folder, as the scanner sees it. Forward slashes, as
    `update_control_file` always wrote them."""
    return "/".join([scanner_dir.replace("\\", "/").rstrip("/"), date, file_name])


def append_to_control_file(control_file: str, line: str) -> bool:
    """Put `line` before the trailing `wait`, the way `update_control_file` does:
    drop the `wait`, append, add `wait` again, rewrite the file. False if the
    line is already in the file, which a restarted script must not add twice.

    Unlike `update_control_file`, blank lines after the `wait` and a last line
    without a newline - what a hand edit leaves behind - do not make it keep a
    `wait` in the middle of the list."""
    with open(control_file, "r") as f:
        lines = f.read().splitlines()

    if any(existing.strip() == line for existing in lines):
        return False

    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == WAIT:
        lines.pop()

    with open(control_file, "w") as f:
        f.writelines(existing + "\n" for existing in lines + [line, WAIT])
    return True


def write_atomic(path: str, data: bytes) -> None:
    """Write to `<path>.tmp`, then rename, so nobody reads half a file - as
    `download_file_atomic` does."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def wait_until_stable(
    path: str,
    check: Callable[[], None] = lambda: None,
    interval: float = 1.0,
    stable_checks: int = 2,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Wait for the interpreter to finish writing `path`: it exists and its size
    did not change for `stable_checks` checks in a row (as
    `wait_until_local_file_is_stable` does). `check` runs on every round and
    ends the wait by raising - which is how a skip or a timeout gets in."""
    last_size, stable = -1, 0
    while True:
        check()
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size == last_size:
                stable += 1
                if stable >= stable_checks:
                    return
            else:
                stable = 0
            last_size = size
        sleep(interval)


# =============================================================================
# Talking to the gateway
# =============================================================================


class SessionEnded(Exception):
    """The gateway does not know this script's session (any more). Nothing
    helps but a new script from `/scanner/new`."""


class JobEnded(Exception):
    """The gateway refused a report for the job: it ended there (it was failed
    for an offline scanner, or its session ended), so it is dropped here."""


class Api:
    """`/scanner/api/*`, authenticated by the runner secret. Network failures and
    server errors are retried with backoff for as long as it takes (the site's
    connection is expected to come back), anything else is raised."""

    def __init__(self, base_url: str, secret: str, say: Callable[..., None]) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.say = say

    def request(self, method: str, path: str, data: Optional[bytes] = None, headers: Optional[dict] = None, auth: bool = True, timeout: float = 60):
        """`(status, body)` of the response."""
        url = path if path.startswith("http") else self.base_url + path
        headers = dict(headers or {})
        if auth:
            headers["Authorization"] = "Bearer " + self.secret
        delay = POLL_INTERVAL
        while True:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as res:
                    return res.status, res.read()
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code in (401, 410):
                    raise SessionEnded(body)
                if e.code < 500:
                    raise JobEnded("{} {}: {} {}".format(method, path, e.code, body))
                problem = "server error {}".format(e.code)
            except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
                problem = "network error ({})".format(getattr(e, "reason", e))
            self.say("{} - retrying in {:.0f} s".format(problem, delay), YELLOW)
            time.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF)

    def next_job(self, have: List[str]) -> Optional[dict]:
        """The next job the script does not `have` yet, if the gateway has one
        for it."""
        query = "?have=" + ",".join(have) if have else ""
        status, body = self.request("GET", "/scanner/api/next" + query)
        return json.loads(body) if status == 200 else None

    def report(self, job_id: str, state: str, message: str = "", log: Optional[List[str]] = None) -> None:
        body = json.dumps({"state": state, "message": message, "log": log or []}).encode()
        self.request(
            "POST",
            "/scanner/api/jobs/{}/state".format(job_id),
            body,
            {"Content-Type": "application/json"},
        )

    def upload(self, job_id: str, name: str, data: bytes, headers: Optional[dict] = None) -> None:
        headers = dict(headers or {})
        headers["X-Content-SHA256"] = hashlib.sha256(data).hexdigest()
        headers["Content-Type"] = "application/octet-stream"
        self.request("PUT", "/scanner/api/jobs/{}/files/{}".format(job_id, name), data, headers, timeout=600)

    def download(self, url: str) -> bytes:
        # The files route needs no credentials, the hash is the permission
        return self.request("GET", url, auth=False)[1]


# =============================================================================
# The console
# =============================================================================


# ANSI styles for `Console.paint`
RED, GREEN, YELLOW, CYAN, BOLD, DIM = "31", "32", "33", "36", "1", "2"


def _enable_windows_colors() -> bool:
    """Windows 10 and later understand ANSI codes once the console is switched
    to it (ENABLE_VIRTUAL_TERMINAL_PROCESSING); older ones refuse."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # standard output
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def colors_supported(stream=None) -> bool:
    """Colors only on a terminal that shows them - not when the output goes to
    a file, nor with `NO_COLOR` set (https://no-color.org). `FORCE_COLOR` turns
    them on regardless."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if type(stream).__module__.startswith("ipykernel"):
        # Spyder's IPython console and Jupyter show colors, but their stdout
        # is no terminal and says so via `isatty()`
        return True
    if not getattr(stream, "isatty", lambda: False)():
        return False
    if os.name == "nt":
        return _enable_windows_colors()
    return os.environ.get("TERM") != "dumb"


def size(n_bytes: int) -> str:
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if n_bytes >= scale:
            return "{:.1f} {}".format(n_bytes / scale, unit)
    return "{} B".format(n_bytes)


def took(since: float) -> str:
    """How long ago the `time.monotonic()` value `since` was."""
    return duration(time.monotonic() - since)


def duration(seconds: float) -> str:
    if seconds < 60:
        return "{:.1f} s".format(seconds)
    return "{:d} min {:02d} s".format(int(seconds // 60), int(seconds % 60))


class Console:
    """What the operator sees. Every line also goes to the gateway with the
    next report, so the gateway's log shows what happened at the site - without
    the colors."""

    def __init__(self, colors: Optional[bool] = None) -> None:
        self.pending = []  # type: List[str]
        self.lock = threading.Lock()
        self.colors = colors_supported() if colors is None else colors

    def paint(self, text: str, *styles: str) -> str:
        if not self.colors or not styles:
            return text
        return "\033[{}m{}\033[0m".format(";".join(styles), text)

    def say(self, message: str, *styles: str) -> None:
        stamp = "[{}]".format(datetime.now().strftime("%H:%M:%S"))
        print("{} {}".format(self.paint(stamp, DIM), self.paint(message, *styles)), flush=True)
        with self.lock:
            self.pending.append("{} {}".format(stamp, message))

    def take(self) -> List[str]:
        with self.lock:
            lines, self.pending = self.pending, []
        return lines


class SkipReader:
    """Reads the console on a thread of its own, so typing `s` + Enter can stop
    the wait for a measurement on Windows as well as Linux (no `select` on a
    Windows console)."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdin
        self.requested = threading.Event()

    def start(self) -> "SkipReader":
        threading.Thread(target=self._read, daemon=True).start()
        return self

    def _read(self) -> None:
        for line in self.stream:
            if line.strip().lower() == "s":
                self.requested.set()


class Skipped(Exception):
    pass


# =============================================================================
# Restart safety
# =============================================================================
# The jobs in flight and how far each got, so a restarted script carries on with
# them rather than appending them to the control file a second time. The gateway
# hands a restarted script the same jobs again; this says what was already done.


class State:
    def __init__(self, path: str, session: str) -> None:
        self.path = path
        # Which session the file is about: a script of a new session must not
        # resume the jobs of an old one.
        self.session = session

    def _read(self) -> dict:
        try:
            with open(self.path, "r") as f:
                state = json.load(f)
        except (OSError, ValueError):
            return {}
        if state.get("session") != self.session:
            return {}
        if "jobs" not in state and "job" in state:
            # Written by a script that had one job at a time
            return {state["job"]: state}
        return state.get("jobs") or {}

    def load(self, job_id: str) -> dict:
        return dict(self._read().get(job_id) or {})

    def save(self, job_id: str, entry: dict) -> None:
        jobs = self._read()
        jobs[job_id] = entry
        write_atomic(self.path, json.dumps({"session": self.session, "jobs": jobs}).encode())

    def drop(self, job_id: str) -> None:
        jobs = self._read()
        jobs.pop(job_id, None)
        if jobs:
            write_atomic(self.path, json.dumps({"session": self.session, "jobs": jobs}).encode())
            return
        try:
            os.remove(self.path)
        except OSError:
            pass


# =============================================================================
# The loop
# =============================================================================
# The script holds up to two jobs: the one being measured, and the next one,
# which is already in the control file so that the interpreter starts it as soon
# as the measurement before it ends - converting and uploading happen during the
# next measurement, not between the two. How many it may hold is the gateway's
# to decide (`MAX_IN_FLIGHT` there): everything else stays in its queue, where
# it can still be cancelled.


class Job:
    """A job the script has: what the gateway sent, its entry in the state
    file and where its files are."""

    def __init__(self, job: dict, entry: dict, measurement_dir: str) -> None:
        self.id = job["id"]
        self.job = job
        self.entry = entry
        self.name = "mrx_{}.seq".format(self.id)
        self.seq_path = os.path.join(measurement_dir, entry["date"], self.name)
        self.dat_path = self.seq_path + ".dat"


class Runner:
    def __init__(self, args, api: Api, console: Console, skip: SkipReader) -> None:
        self.args = args
        self.api = api
        self.console = console
        self.say = console.say
        self.skip = skip
        # Oldest first; the first is the one being measured
        self.jobs = []  # type: List[Job]
        # Why `--simulate` could not write the data, which ends the wait like a skip
        self.simulate_failed = None  # type: Optional[str]
        session = hashlib.sha256(api.secret.encode()).hexdigest()[:16]
        self.state = State(os.path.join(args.measurement_dir, STATE_FILE), session)

    def run(self) -> None:
        """Poll, finish the oldest job while the next one waits in the control
        file, repeat - until the session ends."""
        while True:
            self.take_more()
            if not self.jobs:
                time.sleep(self.args.poll_interval)
                continue
            job = self.jobs[0]
            try:
                self.finish(job)
            except JobEnded as e:
                self.say("job {} was ended by the gateway: {}".format(job.id, e), RED)
            self.jobs.pop(0)
            self.state.drop(job.id)

    def report(self, job: dict, state: str, message: str = "") -> None:
        self.api.report(job["id"], state, message, self.console.take())

    def take_more(self) -> None:
        """Take every job the gateway hands out beyond the ones the script has:
        after a restart those it already had, otherwise at most the next one.
        Every call is also a heartbeat."""
        while True:
            have = [j.id for j in self.jobs]
            job = self.api.next_job(have)
            # A gateway from before `have` hands out the job in flight again
            if job is None or job["id"] in have:
                return
            try:
                self.jobs.append(self.start(job))
            except JobEnded as e:
                # The .seq could not be downloaded
                self.say("job {} failed: {}".format(job["id"], e), RED)
                try:
                    self.report(job, "failed", str(e))
                except JobEnded:
                    pass

    def start(self, job: dict) -> Job:
        """Write the job's `.seq` and append it to the control file, behind the
        measurement in progress if there is one."""
        entry = self.state.load(job["id"])
        name = "mrx_{}.seq".format(job["id"])
        if entry:
            self.say("resuming job {} from {} ({})".format(job["id"], job["login"], name), BOLD, CYAN)
        else:
            self.say("job {} from {}: {}".format(job["id"], job["login"], name), BOLD, CYAN)
            entry = {"date": datetime.now().strftime("%Y%m%d"), "stage": "new"}
        new = Job(job, entry, self.args.measurement_dir)

        # Restarted in the middle of an upload: the data is already there
        if job["state"] != "uploading" and entry["stage"] == "new":
            os.makedirs(os.path.dirname(new.seq_path), exist_ok=True)
            # Written before its line goes into the control file, so the
            # interpreter never finds a path that is not complete yet
            t = time.monotonic()
            seq = self.api.download(job["sequence_url"])
            write_atomic(new.seq_path, seq)
            self.say("downloaded {} ({}) in {}".format(name, size(len(seq)), took(t)), DIM)
            if self.args.control_file is not None:
                line = scanner_path(self.args.scanner_measurement_dir, entry["date"], name)
                if append_to_control_file(self.args.control_file, line):
                    self.say("added to control file: {}".format(line))
            entry["stage"] = "appended"
            self.state.save(new.id, entry)
        if self.jobs:
            self.say("{} is measured next, after {}".format(name, self.jobs[-1].name))
        return new

    def finish(self, job: Job) -> None:
        """Wait for the job's data and upload it."""
        if job.job["state"] == "uploading":
            if not os.path.exists(job.dat_path):
                self.report(job.job, "failed", "the script restarted and {} is gone".format(job.dat_path))
                return
        else:
            # The interpreter is on it now: the one before it is done
            self.report(job.job, "measuring")
            self.simulate_failed = None
            if self.args.simulate and not os.path.exists(job.dat_path):
                threading.Thread(target=self.simulate, args=(job,), daemon=True).start()

            self.say("waiting for {} (type s + Enter to skip)".format(os.path.basename(job.dat_path)))
            try:
                self.wait_for(job)
            except Skipped as e:
                self.say("job {} failed: {}".format(job.id, e), RED)
                self.report(job.job, "failed", str(e))
                return
            # Counted from when the job's turn came, so it includes the
            # interpreter starting up and the file settling
            self.say(
                "{} complete ({}) after {} of measuring".format(
                    os.path.basename(job.dat_path),
                    size(os.path.getsize(job.dat_path)),
                    duration(time.time() - job.entry["measuring_since"]),
                ),
                DIM,
            )

        self.in_background(self.upload, job)

    def wait_for(self, job: Job) -> None:
        self.skip.requested.clear()
        started = job.entry.setdefault("measuring_since", time.time())
        self.state.save(job.id, job.entry)
        last_beat = [time.monotonic()]

        def check() -> None:
            if self.skip.requested.is_set():
                raise Skipped("skipped by operator")
            if self.simulate_failed:
                raise Skipped(self.simulate_failed)
            if self.args.timeout and time.time() - started > self.args.timeout * 60:
                raise Skipped("no data after {:g} minutes (--timeout)".format(self.args.timeout))
            # Measuring can take long, and the gateway counts a silent scanner
            # as offline after 30 s. The report also hears of a job the
            # gateway ended, and the poll takes the next job once there is one.
            if time.monotonic() - last_beat[0] >= self.args.poll_interval:
                self.report(job.job, "measuring")
                self.take_more()
                last_beat[0] = time.monotonic()

        wait_until_stable(job.dat_path, check)

    def in_background(self, work: Callable, *args) -> None:
        """Run `work` on a thread of its own and keep polling meanwhile: reading
        a large `.seq.dat` and uploading can take longer than the gateway waits
        for a sign of life, and a job that comes in meanwhile is appended
        without waiting for the upload."""
        errors = []  # type: List[BaseException]

        def target() -> None:
            try:
                work(*args)
            except BaseException as e:
                errors.append(e)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        while True:
            thread.join(self.args.poll_interval)
            if not thread.is_alive():
                break
            self.take_more()
        if errors:
            raise errors[0]

    def upload(self, job: Job) -> None:
        """Convert the `.seq.dat` and upload the signal. The `.seq.dat` itself is
        not uploaded - it is several times larger - and stays where it is."""
        dat_name = os.path.basename(job.dat_path)
        try:
            with open(job.seq_path, "r", encoding="utf-8") as f:
                counts = adc_sample_counts(f.read())
            self.say("parsing {} ({})".format(dat_name, size(os.path.getsize(job.dat_path))), DIM)
            t = time.monotonic()
            with open(job.dat_path, "r", encoding="ascii") as f:
                samples = read_dat(f)
            self.say("parsed {} lines in {}, converting".format(len(samples), took(t)), DIM)
            t = time.monotonic()
            signal = convert(samples, counts, self.args.coils, self.args.adc_padding)
            del samples
            if CONJUGATE:
                np.conjugate(signal, out=signal)
            self.say(
                "converted to {} x {} coils ({} ADCs{}) in {}".format(
                    signal.shape[0], signal.shape[1], len(counts), ", conjugated" if CONJUGATE else "", took(t)
                ),
                DIM,
            )
        except (ValueError, UnicodeDecodeError) as e:
            # Whoever looks into it needs the raw file, which only the site has
            message = "{} - the raw data stays at the site, in {}".format(e, job.dat_path)
            self.say("job {} failed: {}".format(job.id, message), RED)
            self.report(job.job, "failed", message)
            return

        if job.job["state"] != "uploading":
            self.report(job.job, "uploading")
        shape = signal.shape
        data = npy_bytes(signal)
        del signal
        self.say("uploading signal.npy ({})".format(size(len(data))), DIM)
        t = time.monotonic()
        self.api.upload(job.id, "signal.npy", data, {"X-Signal-Shape": "{},{}".format(*shape)})
        seconds = time.monotonic() - t
        self.say(
            "uploaded in {} ({:.1f} MB/s)".format(duration(seconds), len(data) / 1e6 / max(seconds, 1e-3)), DIM
        )
        # The gateway has the signal now, so the job is done there. This line
        # reaches the gateway's log with the next report.
        self.say("job {} done: signal {} x {} coils uploaded".format(job.id, *shape), GREEN)

    def simulate(self, job: Job) -> None:
        """Play the interpreter: wait a bit, check that the job is in the
        control file (if there is one), and write noise in its layout where the
        real data would go. The script only calls this for the job whose turn
        it is, as the interpreter measures one after the other."""
        time.sleep(self.args.simulate_delay)
        if self.args.control_file is not None:
            line = scanner_path(self.args.scanner_measurement_dir, job.entry["date"], job.name)
            with open(self.args.control_file, "r") as f:
                lines = [l.strip() for l in f]
            if line not in lines:
                self.say("simulate: this job is not in the control file, writing nothing", YELLOW)
                return
        try:
            with open(job.seq_path, "r", encoding="utf-8") as f:
                counts = adc_sample_counts(f.read())
        except (ValueError, UnicodeDecodeError) as e:
            # What the interpreter would choke on too
            self.simulate_failed = "simulate: cannot read {}: {}".format(job.name, e)
            return
        write_atomic(job.dat_path, fake_dat(counts, self.args.coils, self.args.adc_padding).encode())
        self.say("simulate: wrote {}".format(os.path.basename(job.dat_path)), DIM)


# =============================================================================
# Settings
# =============================================================================


def ask(prompt: str, default) -> str:
    """One setting typed in, the default when Enter is pressed."""
    shown = " [{}]".format(default) if default not in (None, "") else ""
    while True:
        try:
            answer = input("{}{}: ".format(prompt, shown)).strip()
        except EOFError:
            answer = ""
        if answer:
            return answer
        if default not in (None, ""):
            return str(default)
        print("  this one has no default, please enter a value")


def settings(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        description="Connects this scanner to the MRX gateway: measures the sequences sent to it and uploads the data."
    )
    parser.add_argument("--measurement-dir", help="measurement folder, as this PC sees it")
    parser.add_argument("--scanner-measurement-dir", help="the same folder, as the scanner sees it")
    parser.add_argument("--control-file", help="the Pulseq interpreter's control file")
    parser.add_argument("--coils", type=int, help="receive coils in the .seq.dat")
    parser.add_argument("--adc-padding", type=int, help="extra samples per coil readout")
    parser.add_argument("--timeout", type=float, default=None, help="give up on a job after this many minutes (default: off)")
    parser.add_argument("--simulate", action="store_true", help="also play the interpreter, writing noise as the data")
    parser.add_argument("--simulate-delay", type=float, default=3.0, help=argparse.SUPPRESS)
    parser.add_argument("--poll-interval", type=float, default=POLL_INTERVAL, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    # Asked for only when not given, so for this site Enter is the usual answer
    if args.measurement_dir is None:
        if args.simulate:
            # Simulated data does not belong with the real measurements
            default = os.path.join(tempfile.gettempdir(), "mrx_scanner_simulate")
            args.measurement_dir = ask("Measurement folder (this PC)", default)
            if args.measurement_dir == default:
                os.makedirs(default, exist_ok=True)
        else:
            args.measurement_dir = ask("Measurement folder (this PC)", DEFAULT_MEASUREMENT_DIR)
    if args.scanner_measurement_dir is None:
        if args.simulate:
            # When simulating, this PC is the scanner too
            args.scanner_measurement_dir = args.measurement_dir
        else:
            args.scanner_measurement_dir = ask("Measurement folder (as the scanner sees it)", DEFAULT_SCANNER_MEASUREMENT_DIR)
    # When simulating, no interpreter reads a control file, so it is only used
    # when given
    if args.control_file is None and not args.simulate:
        args.control_file = ask("Control file", DEFAULT_CONTROL_FILE)
    if args.coils is None:
        args.coils = int(ask("Receive coils", DEFAULT_COILS))
    if args.adc_padding is None:
        args.adc_padding = int(ask("Extra samples per coil readout", DEFAULT_ADC_PADDING))

    problems = []
    if not os.path.isdir(args.measurement_dir):
        problems.append("measurement folder does not exist: " + args.measurement_dir)
    elif not os.access(args.measurement_dir, os.W_OK):
        problems.append("measurement folder is not writable: " + args.measurement_dir)
    if args.control_file is not None:
        if not os.path.isfile(args.control_file):
            problems.append("control file does not exist: " + args.control_file)
        elif not os.access(args.control_file, os.W_OK):
            problems.append("control file is not writable: " + args.control_file)
    if args.coils < 1 or args.adc_padding < 0:
        problems.append("--coils must be at least 1 and --adc-padding not negative")
    if problems:
        parser.error("; ".join(problems))
    return args


def command_line(args) -> str:
    def quote(value) -> str:
        value = str(value)
        return '"{}"'.format(value) if " " in value else value

    parts = [
        "python", quote(os.path.basename(sys.argv[0]) or "mrx_scanner.py"),
        "--measurement-dir", quote(args.measurement_dir),
        "--scanner-measurement-dir", quote(args.scanner_measurement_dir),
    ]
    if args.control_file is not None:
        parts += ["--control-file", quote(args.control_file)]
    parts += [
        "--coils", str(args.coils),
        "--adc-padding", str(args.adc_padding),
    ]
    if args.timeout:
        parts += ["--timeout", "{:g}".format(args.timeout)]
    if args.simulate:
        parts.append("--simulate")
    return " ".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    if not RUNNER_SECRET.startswith("scr_"):
        print("This is the template. Download your own script at https://mrx-org.github.io/scanner/.")
        return 2

    args = settings(argv)
    console = Console()
    paint = console.paint
    print("\nNext time, the same settings are:\n  {}\n".format(paint(command_line(args), DIM)))
    print("MRX scanner session of {} at {}".format(paint(OPERATOR, BOLD), BASE_URL))
    print("Scan token (give it to who may measure here): {}".format(paint(SCAN_TOKEN, BOLD, CYAN)))
    if CONJUGATE:
        print("Signal is complex conjugated before upload\n")
    else:
        print(paint("Signal is NOT complex conjugated before upload", YELLOW) + "\n")
    if numpy_too_old_for_fast_loadtxt():
        # `np.loadtxt` only has a fast parser (in C) since 1.23; before that it
        # is pure Python, slow and several times as hungry for memory
        bar = "!" * 72
        lines = [
            bar,
            "WARNING: numpy {} is old (older than 1.23)".format(np.__version__),
            "Reading back large signals (.seq.dat) may be very slow and use a lot",
            "of memory. Update numpy to 1.23 or newer if you can.",
            bar,
        ]
        print("\n".join(paint(line, BOLD, RED) for line in lines) + "\n")
    if args.simulate:
        print(paint("SIMULATING: no scanner is used, the data is noise", BOLD, YELLOW) + "\n")

    api = Api(BASE_URL, RUNNER_SECRET, console.say)
    runner = Runner(args, api, console, SkipReader().start())
    console.say("waiting for sequences")
    try:
        runner.run()
    except SessionEnded as e:
        console.say(str(e) or "session expired - get a new script at {}/scanner/new".format(BASE_URL), RED)
        return 1
    except KeyboardInterrupt:
        console.say("stopped", YELLOW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
