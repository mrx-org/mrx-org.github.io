# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.28",
#     "numpy>=1.23",
#     "textual>=8",
# ]
# ///
"""The scanner-side script: runs on the bridge PC next to a scanner, takes the
sequences queued for it from the gateway, has the scanner measure them and
uploads what it measured. Start it with `uv run mrx_scanner.py`.

How the scanner side works (Pulseq interpreter, `control.txt`, `position.txt`,
the ICE program and `sync.bat`) is described in `docs/scan/scanner-setup.md` in
the mcp-gateway repo, and the pipeline in `docs/scan/redesign.md`.

In short: the script downloads every job at once, drops one at a time (or
`--lookahead`) into the share's `inbox\\`, from where `sync.bat` puts it into
`control.txt`, reads what the scanner does from the share's `status\\`, and
converts and uploads each `.seq.dat` once it is there.

This file lives only here, next to the session page on mrx-org.github.io
(`docs/scanner/`), which hands it out with a session's secrets filled in. The
gateway keeps its own copy of `adc_sample_counts` (`scan/seq.py`) - change both
together.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import secrets
import shutil
import sys
import time
import warnings
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Callable, Protocol

import numpy as np
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Label, RichLog, Static

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

VERSION = "2.0.0-dev"

# The defaults for the site this was built for; every one can be overridden
DEFAULT_SHARE = r"W:\neuroradiologie\zaiss-mrx"
DEFAULT_COILS = 20
DEFAULT_ADC_PADDING = 4

# How often the script talks to the gateway: often while a job is on its way,
# less when idle - a new job waits at most this long while the scanner is free.
# The Cloudflare Workers free plan allows 100,000 requests a day for everything;
# 5 s is about 17,000 a day.
SYNC_ACTIVE = 2.0  # seconds
SYNC_IDLE = 5.0  # seconds
# `sync.bat` writes its heartbeat every ~3 s. One that has not changed for this
# long means it is not running.
SYNC_BAT_TIMEOUT = 15.0  # seconds

FINAL = frozenset({"done", "cancelled", "failed", "expired"})
# The reason a cancel gets when it comes without one. Aborts on the scanner get
# theirs from the data ("aborted on the scanner after k of K ADCs").
CANCEL_REASONS = {
    "operator": "cancelled by the operator in the scanner script",
    "agent": "cancelled with scan_cancel",
}
WAIT = "wait"
SCRIPT_DIR = Path(__file__).resolve().parent


class ScanError(Exception):
    """A failure meant for the operator, worded for them."""


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


def _sections(seq_text: str) -> dict:
    sections: dict = {}
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
    return sections


def adc_sample_counts(seq_text: str) -> list[int]:
    """`num_samples` of every ADC event, in the order the blocks play them."""
    sections = _sections(seq_text)
    adc_nums = {int(cols[0]): int(cols[_ADC_NUM_COLUMN - 1]) for cols in sections.get("[ADC]", [])}

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


def seq_duration(seq_text: str) -> float | None:
    """`TotalDuration` from `[DEFINITIONS]` in seconds, if the sequence has it."""
    for cols in _sections(seq_text).get("[DEFINITIONS]", []):
        if cols[0] == "TotalDuration" and len(cols) > 1:
            try:
                return float(cols[1])
            except ValueError:
                return None
    return None


def demo_seq(adcs: int, samples: int, duration: float) -> str:
    """A minimal Pulseq file with `adcs` readouts, enough for everything this
    script reads from a sequence. For `--demo` and the tests."""
    blocks = "\n".join("{} 100 0 0 0 0 1 0".format(i + 1) for i in range(adcs))
    return (
        "# made by mrx_scanner.py --demo\n[VERSION]\nmajor 1\nminor 4\nrevision 1\n\n"
        "[DEFINITIONS]\nTotalDuration {:g}\n\n"
        "[BLOCKS]\n# id dur rf gx gy gz adc ext\n{}\n\n"
        "[ADC]\n# id num dwell delay q phi\n1 {} 10000 0 0 0\n".format(duration, blocks, samples)
    )


# =============================================================================
# `.seq.dat` -> `signal.npy`
# =============================================================================
# The ICE program writes one `<re> <im>` line per sample, nested ADC -> coil ->
# sample, with `padding` samples nobody understands at the end of every coil's
# readout (see `docs/scan/dat-format.md`). What `scan` hands out is the same
# signal as `(ADC samples, coils)`: row k is sample k of every coil.


def expected_lines(adc_counts: list[int], coils: int, padding: int) -> int:
    return coils * sum(n + padding for n in adc_counts)


def whole_adcs(n_lines: int, adc_counts: list[int], coils: int, padding: int) -> int | None:
    """How many ADCs `n_lines` lines hold, if they end exactly after one. An
    aborted measurement leaves such a `.seq.dat`: fewer ADCs, but whole ones."""
    total = 0
    for k, n in enumerate(adc_counts):
        if total == n_lines:
            return k
        total += coils * (n + padding)
    return len(adc_counts) if total == n_lines else None


def read_dat(dat) -> np.ndarray:
    """Every `<re> <im>` line of a `.seq.dat` (a path or an open text file) as
    one flat complex64 array, in file order. Raises `ValueError` if a line is
    not two numbers."""
    try:
        with warnings.catch_warnings():
            # An empty file is no different from one cut short: the caller says so
            warnings.simplefilter("ignore", UserWarning)
            values = np.loadtxt(dat, dtype=np.float32, ndmin=2)
    except ValueError as e:
        raise ValueError("every line of the .seq.dat must be '<re> <im>': {}".format(str(e).split(";")[0]))
    if values.size == 0:
        return np.zeros(0, dtype="<c8")
    if values.shape[1] != 2:
        raise ValueError("every line of the .seq.dat must be '<re> <im>', these have {} values".format(values.shape[1]))
    return np.ascontiguousarray(values, dtype="<f4").view("<c8").ravel()


def convert(samples: np.ndarray, adc_counts: list[int], coils: int, padding: int) -> np.ndarray:
    """The samples from `read_dat` as complex64 of shape `(ADC samples, coils)`.
    Raises `ValueError` if they do not have the layout the arguments describe."""
    expected = expected_lines(adc_counts, coils, padding)
    if len(samples) != expected:
        raise ValueError(
            "the .seq.dat has {} lines, but {} coils x (ADC samples + {} padding) "
            "for this sequence make {} - check --coils and --adc-padding".format(len(samples), coils, padding, expected)
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


def write_fake_dat(path: Path, adc_counts: list[int], coils: int, padding: int, rng=None) -> None:
    """Noise in the ICE program's layout, which the simulated scanner writes in
    place of a measurement - so the conversion runs on it too."""
    lines = expected_lines(adc_counts, coils, padding)
    data = (rng or np.random.default_rng()).standard_normal((lines, 2)).astype(np.float32)
    tmp = path.with_name(path.name + ".tmp")
    np.savetxt(tmp, data, fmt="%.6f")
    os.replace(tmp, path)


def write_atomic(path: Path, data: bytes) -> None:
    """Write to `<path>.tmp`, then rename, so nobody reads half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def size(n_bytes: float) -> str:
    for unit in ("B", "kB", "MB"):
        if n_bytes < 1000:
            return "{:.0f} {}".format(n_bytes, unit) if unit == "B" else "{:.1f} {}".format(n_bytes, unit)
        n_bytes /= 1000
    return "{:.1f} GB".format(n_bytes)


def clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return "{}:{:02d}".format(seconds // 60, seconds % 60)


# =============================================================================
# The share: inbox, status, measurement
# =============================================================================
# See `docs/scan/scanner-setup.md`. The script writes only into `inbox\\` (and
# its converted signals next to the `.seq.dat`); everything else is `sync.bat`'s.


@dataclass
class ScannerStatus:
    """What `sync.bat` last published: its run, its round, its date, the
    interpreter's `control.txt` and how many lines of it it has read."""

    run: str
    beat: int
    today: str
    lines: list[str]
    position: int

    def find(self, name: str) -> tuple[int, str] | None:
        """Line (from 1) and date folder of the `.seq` called `name`."""
        for i, line in enumerate(self.lines, 1):
            path = PureWindowsPath(line.strip())
            if path.name == name:
                return i, path.parent.name
        return None


class Share:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.inbox = self.root / "inbox"
        self.status_dir = self.root / "status"
        self.measurement = self.root / "measurement"

    def check(self) -> list[str]:
        """What is missing for the script to work."""
        if not self.root.is_dir():
            return ["share not found: {}".format(self.root)]
        if not self.inbox.is_dir():
            return ["no inbox at {} - is the new sync.bat running on the scanner PC?".format(self.inbox)]
        return []

    def drop(self, name: str, data: bytes) -> None:
        write_atomic(self.inbox / name, data)

    def in_inbox(self, name: str) -> bool:
        return (self.inbox / name).exists()

    def withdraw(self, name: str) -> bool:
        """Take a file back out of the inbox. False if `sync.bat` has it already."""
        try:
            (self.inbox / name).unlink()
            return True
        except FileNotFoundError:
            return False

    def read_status(self) -> ScannerStatus | None:
        try:
            beat = (self.status_dir / "heartbeat.txt").read_text().split()
            lines = (self.status_dir / "control.txt").read_text(errors="replace").splitlines()
            position = int((self.status_dir / "position.txt").read_text().strip() or 0)
            return ScannerStatus(beat[0], int(beat[1]), beat[2], lines, position)
        except (OSError, ValueError, IndexError):
            return None

    def dat(self, day: str, name: str) -> Path:
        return self.measurement / day / (name + ".dat")

    def dat_in_transfer(self, day: str, name: str) -> bool:
        return (self.measurement / day / (name + ".dat.tmp")).exists()


class SimulatedScanner:
    """Plays `sync.bat`, the Pulseq interpreter and the ICE program on a local
    folder with the share's layout, for `--simulate`. Every `tick` is one round
    of `sync.bat`; a measurement takes the sequence's `TotalDuration` (or
    `duration`) and then writes noise as its `.seq.dat`."""

    HOST = r"C:\ProgramData\Siemens\Numaris\MriCustomer\CustomerSeq\pulseq\seq-files\measurement"

    def __init__(self, share: Share, coils: int, padding: int, duration: float | None = None) -> None:
        self.share = share
        self.coils = coils
        self.padding = padding
        self.duration = duration
        for folder in (share.inbox, share.status_dir, share.measurement):
            folder.mkdir(parents=True, exist_ok=True)
        self.beat = 0
        self.current: dict | None = None
        self.restart()

    def restart(self) -> None:
        """What a restart of `sync.bat` does: a fresh `control.txt`. A
        measurement in progress goes on."""
        self.run = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        self.lines: list[str] = []
        self.position = 0
        self._publish()

    def abort(self) -> bool:
        """The supervisor stops the measurement: half of it is written."""
        if self.current is None:
            return False
        self._finish(abort=True)
        return True

    def tick(self) -> None:
        today = datetime.now().strftime("%Y%m%d")
        for seq in sorted(self.share.inbox.glob("*.seq")):
            if not any(PureWindowsPath(line).name == seq.name for line in self.lines):
                self.lines.append("{}\\{}\\{}".format(self.HOST, today, seq.name))
            target = self.share.measurement / today / seq.name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(seq, target)

        if self.current is not None and time.monotonic() >= self.current["end"]:
            self._finish()
        if self.current is None and self.position < len(self.lines) and self.lines[self.position].strip() != WAIT:
            path = PureWindowsPath(self.lines[self.position])
            self.position += 1
            seq = self.share.measurement / path.parent.name / path.name
            text = seq.read_text()
            duration = self.duration if self.duration is not None else seq_duration(text) or 5.0
            self.current = {"seq": seq, "counts": adc_sample_counts(text), "end": time.monotonic() + duration}
        self._publish()

    def _finish(self, abort: bool = False) -> None:
        seq, counts = self.current["seq"], self.current["counts"]
        if abort:
            counts = counts[: len(counts) // 2]
        write_fake_dat(seq.with_name(seq.name + ".dat"), counts, self.coils, self.padding)
        self.current = None

    def _publish(self) -> None:
        self.beat += 1
        status = self.share.status_dir
        write_atomic(status / "control.txt", ("\r\n".join(self.lines + [WAIT]) + "\r\n").encode())
        write_atomic(status / "position.txt", "{} \r\n".format(self.position).encode())
        today = datetime.now().strftime("%Y%m%d")
        write_atomic(status / "heartbeat.txt", "{} {} {}\r\n".format(self.run, self.beat, today).encode())


# =============================================================================
# The gateway
# =============================================================================
# What the engine needs from the gateway (`POST /scanner/api/sync` and the R2
# upload in `docs/scan/redesign.md`). Only the demo exists so far; the HTTP
# client comes with the gateway's side.


class Gateway(Protocol):
    async def sync(self, report: dict) -> dict:
        """Send the script's view, get `{"jobs": [...], "cancel": [...], "version": ...}`."""

    async def download(self, job: "Job") -> bytes: ...

    async def upload(self, job: "Job", path: Path, progress: Callable[[int, int], None]) -> None: ...

    async def abort_upload(self, job: "Job") -> None: ...

    async def retry(self, job: "Job", mode: str) -> dict:
        """A new job for `job`, which the gateway records as its retry."""


class SessionEnded(Exception):
    """The gateway no longer knows this script's session (expired or unknown)."""


class HttpGateway:
    """The gateway's `/scanner/api/*`. The signal goes up as a multipart
    upload: the gateway hands out one URL per part (R2, presigned), and the
    parts go there directly, `streams` at a time."""

    def __init__(self, base_url: str, secret: str, part_size: int = 16 * 1024 * 1024, streams: int = 4) -> None:
        import httpx

        self.httpx = httpx
        self.base_url = base_url.rstrip("/")
        self.part_size = part_size
        self.streams = streams
        agent = {"User-Agent": "mrx-scanner/" + VERSION}
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60, connect=15), headers={"Authorization": "Bearer " + secret, **agent}
        )
        # Presigned URLs carry their own credentials: no Authorization header
        self.parts = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15), headers=agent)

    def _check(self, res) -> dict:
        if res.status_code in (401, 410):
            raise SessionEnded(res.text or "the session has ended")
        if res.status_code >= 400:
            raise ScanError("{} {}: {} {}".format(res.request.method, res.request.url.path, res.status_code, res.text[:300]))
        return res.json() if res.content else {}

    async def _post(self, path: str, payload: dict | None = None) -> dict:
        return self._check(await self.client.post(self.base_url + path, json=payload or {}))

    async def sync(self, report: dict) -> dict:
        return await self._post("/scanner/api/sync", report)

    async def download(self, job: "Job") -> bytes:
        res = await self.client.get(job.sequence_url)
        if res.status_code != 200:
            raise ScanError("downloading the sequence failed: {} {}".format(res.status_code, res.text[:200]))
        return res.content

    async def upload(self, job: "Job", path: Path, progress: Callable[[int, int], None]) -> None:
        data = await asyncio.to_thread(path.read_bytes)
        sha256 = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())
        start = await self._post(
            "/scanner/api/jobs/{}/upload".format(job.id),
            {"size": len(data), "part_size": self.part_size, "sha256": sha256, "shape": job.shape},
        )
        urls, part_size = start["urls"], start["part_size"]
        sent = [0] * len(urls)
        etags: list[str] = [""] * len(urls)
        gate = asyncio.Semaphore(self.streams)

        async def put(n: int) -> None:
            chunk = data[n * part_size : (n + 1) * part_size]
            async with gate:
                for attempt in range(1, 4):
                    try:
                        res = await self.parts.put(urls[n], content=chunk)
                        res.raise_for_status()
                        etags[n] = res.headers["etag"]
                        sent[n] = len(chunk)
                        progress(sum(sent), len(data))
                        return
                    except (self.httpx.HTTPError, KeyError) as e:
                        if attempt == 3:
                            raise ScanError("part {} of {} failed 3 times: {}".format(n + 1, len(urls), e))
                        await asyncio.sleep(2 * attempt)

        await asyncio.gather(*(put(n) for n in range(len(urls))))
        await self._post("/scanner/api/jobs/{}/upload/complete".format(job.id), {"upload": start["upload"], "etags": etags})

    async def abort_upload(self, job: "Job") -> None:
        await self._post("/scanner/api/jobs/{}/upload/abort".format(job.id))

    async def retry(self, job: "Job", mode: str) -> dict:
        return await self._post("/scanner/api/jobs/{}/retry".format(job.id), {"mode": mode})


class DemoGateway:
    """A gateway in the process, for `--demo`: a few jobs at once, then one
    every `every` seconds, small random sequences, uploads at a few MB/s."""

    NAMES = ("gre_2d", "epi_se", "flash_3d", "tse_t2", "dream", "bssfp", "spiral")
    LOGINS = ("jendres", "agent", "sweinmueller")

    def __init__(self, first: int = 3, every: tuple[float, float] | None = (20, 60), durations=(6, 20), rng=None) -> None:
        self.rng = rng or random.Random()
        self.first = first
        self.every = every
        self.durations = durations
        self._next = time.monotonic() + self.rng.uniform(*every) if every else float("inf")
        self._cancels: list[dict] = []
        self.reports: list[dict] = []

    def new_job(self, **info) -> dict:
        job = {
            "id": secrets.token_urlsafe(6),
            "login": self.rng.choice(self.LOGINS),
            "name": self.rng.choice(self.NAMES),
            "sequence_url": "",
        }
        job.update(info)
        return job

    def request_cancel(self, job_id: str, reason: str = "") -> None:
        """What `scan_cancel` will do: the script hears it with its next sync."""
        self._cancels.append({"job": job_id, "by": "agent", "reason": reason})

    async def sync(self, report: dict) -> dict:
        self.reports.append(report)
        jobs = []
        if self.first:
            jobs, self.first = [self.new_job() for _ in range(self.first)], 0
        elif time.monotonic() >= self._next:
            jobs.append(self.new_job())
            self._next = time.monotonic() + self.rng.uniform(*self.every)
        cancels, self._cancels = self._cancels, []
        return {"jobs": jobs, "cancel": cancels, "version": VERSION}

    async def download(self, job: "Job") -> bytes:
        await asyncio.sleep(self.rng.uniform(0.2, 1.0))
        return demo_seq(self.rng.randint(16, 96), 128, self.rng.uniform(*self.durations)).encode()

    async def upload(self, job: "Job", path: Path, progress: Callable[[int, int], None]) -> None:
        total, sent = path.stat().st_size, 0
        rate = 6e6 * self.rng.uniform(0.5, 1.2)
        while sent < total:
            await asyncio.sleep(0.1)
            sent = min(total, sent + int(rate * 0.1))
            progress(sent, total)

    async def abort_upload(self, job: "Job") -> None:
        pass

    async def retry(self, job: "Job", mode: str) -> dict:
        return self.new_job(login=job.login, name=job.name)


# =============================================================================
# Jobs and the log
# =============================================================================


@dataclass
class Job:
    id: str
    login: str
    name: str
    sequence_url: str = ""
    created: float = field(default_factory=time.time)
    state: str = "downloading"
    message: str = ""
    by: str = ""  # who cancelled it: agent, operator or supervisor
    reason: str = ""
    retry_of: str = ""
    priority: bool = False  # restarted from the TUI: measured next
    duration: float = 0.0  # expected measurement time, from the .seq
    # On the scanner side
    file: str = ""  # its name in the inbox and in control.txt
    day: str = ""  # its date folder, from control.txt
    line: int = 0  # its line in control.txt, from 1
    on_scanner: bool = False  # dropped and its .seq.dat not there yet
    read: bool = False  # the interpreter has read its line
    discard: bool = False  # cancelled once on the scanner: its data is dropped
    measuring_since: float = 0.0
    measured: float = 0.0
    # Results
    npy: str = ""
    shape: list = field(default_factory=list)
    partial: bool = False
    progress: float = 0.0
    rate: float = 0.0  # bytes per second while uploading
    finished: float = 0.0


class EventLog:
    """Every event, as one JSON object per line in `scan-log-<YYYYMMDD>.jsonl`
    in `folder`, to the TUI, and to the gateway with the next sync."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.listeners: list[Callable[[dict], None]] = []
        self.pending: list[dict] = []

    def __call__(self, event: str, message: str, level: str = "info", job: Job | None = None, **extra) -> None:
        record = {"ts": datetime.now().isoformat(timespec="milliseconds"), "level": level, "event": event}
        if job is not None:
            record.update(job=job.id, name=job.name)
        record["message"] = message
        record.update(extra)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder / "scan-log-{}.jsonl".format(datetime.now().strftime("%Y%m%d"))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass  # a full or unreachable disk must not stop the measurement
        self.pending = (self.pending + [record])[-200:]
        for listener in self.listeners:
            listener(record)

    def take(self) -> list[dict]:
        records, self.pending = self.pending, []
        return records


# =============================================================================
# The engine
# =============================================================================


class Engine:
    """Everything the script does, one `tick` at a time: talk to the gateway,
    read what the scanner does, drop the next job, start conversions and
    uploads. The TUI calls `tick` and shows `jobs`; the tests call it directly."""

    def __init__(
        self,
        gateway: Gateway,
        share: Share,
        workdir: Path,
        log: EventLog,
        coils: int = DEFAULT_COILS,
        padding: int = DEFAULT_ADC_PADDING,
        lookahead: int = 1,
        scanner: SimulatedScanner | None = None,
    ) -> None:
        self.gateway = gateway
        self.share = share
        self.log = log
        self.coils = coils
        self.padding = padding
        self.lookahead = lookahead
        self.scanner = scanner
        self.seq_dir = Path(workdir) / "jobs"
        self.seq_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = Path(workdir) / "state.json"
        self.jobs: dict[str, Job] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.status: ScannerStatus | None = None
        self.gateway_online: bool | None = None
        self.sync_bat_alive = False
        self.latest_version = VERSION
        self._next_sync = 0.0
        self._run: str | None = None
        self._beat: int | None = None
        self._beat_seen = 0.0
        self._drops = 0
        self.ended = ""  # why the gateway ended the session, if it did
        self.load()

    # --- the loop --------------------------------------------------------------

    async def tick(self) -> None:
        if self.scanner is not None:
            self.scanner.tick()
        if time.monotonic() >= self._next_sync:
            await self.sync()
        self.observe()
        self.schedule()
        self.save()

    def busy(self) -> bool:
        return any(job.state not in FINAL or job.on_scanner for job in self.jobs.values())

    async def sync(self) -> None:
        if self.ended:
            return
        report = {
            "version": VERSION,
            "sync_bat": self.sync_bat_alive,
            "jobs": {
                job.id: {
                    "state": job.state,
                    "message": job.message,
                    "by": job.by,
                    "reason": job.reason,
                    "has_data": self.has_data(job),
                }
                for job in self.jobs.values()
                if job.state not in FINAL or time.time() - (job.finished or job.created) < 3600
            },
            "log": self.log.take(),
        }
        try:
            answer = await self.gateway.sync(report)
        except SessionEnded as e:
            self.ended = str(e)
            self.log("session.ended", "the session has ended: {} - get a new script".format(e), level="error")
            return
        except Exception as e:  # noqa: BLE001 - the network, reported and retried
            if self.gateway_online is not False:
                self.log("gateway.offline", "gateway not reachable: {}".format(e), level="warning")
            self.gateway_online = False
            self._next_sync = time.monotonic() + SYNC_ACTIVE * 2
            return
        if self.gateway_online is False:
            self.log("gateway.online", "gateway reachable again")
        self.gateway_online = True
        self.latest_version = answer.get("version") or VERSION
        for info in answer.get("jobs", []):
            if info["id"] not in self.jobs:
                self.take(info)
        for request in answer.get("cancel", []):
            job = self.jobs.get(request["job"])
            if job is not None:
                self.cancel(job, request.get("by", "agent"), request.get("reason", ""))
        for final in answer.get("final", []):
            # Ended on the gateway's side (expired, or failed by a timeout)
            job = self.jobs.get(final["job"])
            if job is not None and job.state not in FINAL:
                task = self.tasks.pop(job.id, None)
                if task is not None:
                    task.cancel()
                self.set(job, final["state"], final.get("message", ""), level="warning")
        self._next_sync = time.monotonic() + (SYNC_ACTIVE if self.busy() else SYNC_IDLE)

    def take(self, info: dict) -> Job:
        """A job the gateway handed out: download its sequence - or, for a
        retry that only uploads again, upload the signal this script kept."""
        job = self.add(info, retry_of=info.get("retry_of", ""))
        source = self.jobs.get(info.get("upload_from") or "")
        if info.get("upload_from"):
            if source is None or not self.has_data(source):
                self.set(job, "failed", "this script no longer has the signal of job {}".format(info["upload_from"]))
                return job
            job.npy, job.shape, job.file, job.day = source.npy, source.shape, source.file, source.day
            if self.seq_path(source).exists():
                shutil.copyfile(self.seq_path(source), self.seq_path(job))
            self.log("job.new", "upload again of job {} for {}".format(source.id, job.login), job=job)
            self.spawn(job, self.upload(job))
            return job
        self.log("job.new", "new job from {}".format(job.login), job=job)
        self.spawn(job, self.download(job))
        return job

    def has_data(self, job: Job) -> bool:
        """Whether this script has the job's whole signal, to upload again."""
        return bool(job.npy) and not job.partial and Path(job.npy).exists()

    def add(self, info: dict, **extra) -> Job:
        job = Job(
            id=info["id"],
            login=info.get("login", "?"),
            name=info.get("name") or info["id"],
            sequence_url=info.get("sequence_url", ""),
            **extra,
        )
        self.jobs[job.id] = job
        return job

    def spawn(self, job: Job, coro) -> None:
        """Run `coro` for `job`; a failure fails the job."""

        async def guarded() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001 - shown to the operator
                if job.state not in FINAL:
                    self.set(job, "failed", str(e) or type(e).__name__, level="error")
            finally:
                if self.tasks.get(job.id) is task:
                    del self.tasks[job.id]

        task = asyncio.get_running_loop().create_task(guarded())
        self.tasks[job.id] = task

    def set(self, job: Job, state: str, message: str = "", level: str | None = None) -> None:
        job.state = state
        job.message = message
        if state in FINAL:
            job.finished = time.time()
        self.log("job." + state, message or state, level=level or ("warning" if state == "failed" else "info"), job=job)
        self._next_sync = min(self._next_sync, time.monotonic() + 0.5)  # tell the gateway soon
        self.save()

    # --- steps -----------------------------------------------------------------

    async def download(self, job: Job) -> None:
        data = await self.gateway.download(job)
        self.seq_path(job).write_bytes(data)
        job.duration = seq_duration(data.decode("utf-8", "replace")) or 0.0
        self.set(job, "ready", "downloaded ({})".format(size(len(data))))

    def schedule(self) -> None:
        """Keep `lookahead` jobs dropped but not yet read by the interpreter."""
        waiting = sum(1 for job in self.jobs.values() if job.on_scanner and not job.read)
        ready = sorted(
            (job for job in self.jobs.values() if job.state == "ready"),
            key=lambda job: (not job.priority, job.created),
        )
        for job in ready[: max(0, self.lookahead - waiting)]:
            self._drops += 1
            # The name order is the drop order: sync.bat schedules by name
            stamp = datetime.now().strftime("%y%m%d-%H%M%S")
            job.file = "mrx_{}-{:02d}_{}.seq".format(stamp, self._drops % 100, job.id)
            self.share.drop(job.file, self.seq_path(job).read_bytes())
            job.on_scanner, job.read, job.line, job.day = True, False, 0, ""
            self.set(job, "scheduled", "dropped into the inbox as " + job.file)

    def observe(self) -> None:
        """Read `sync.bat`'s status and move the jobs on the scanner along."""
        status = self.share.read_status()
        now = time.monotonic()
        if status is not None:
            if self._run is not None and status.run != self._run:
                self.scanner_restarted(status)
            self._run = status.run
            if status.beat != self._beat:
                self._beat, self._beat_seen = status.beat, now
        alive = status is not None and now - self._beat_seen < SYNC_BAT_TIMEOUT
        if alive != self.sync_bat_alive:
            if alive:
                self.log("sync_bat.online", "sync.bat is running")
            else:
                self.log("sync_bat.offline", "sync.bat is not running (no heartbeat in {})".format(self.share.status_dir), level="warning")
        self.sync_bat_alive = alive
        self.status = status
        if status is None:
            return

        for job in list(self.jobs.values()):
            if not job.on_scanner:
                continue
            found = status.find(job.file)
            if found is not None:
                job.line, job.day = found
            elif not job.read:
                continue  # still in the inbox, or on its way from there
            # A job already read is looked for even when its line is gone (a
            # restarted sync.bat): its .seq.dat still arrives.
            if not job.read and job.line <= status.position:
                job.read = True
                job.measuring_since = time.time()
                if job.state == "scheduled":
                    self.set(job, "measuring", "the interpreter read line {}".format(job.line))
                else:
                    self.log("job.measured_anyway", "cancelled, but measured anyway: its data will be discarded", job=job)
            if not job.read:
                if job.state == "scheduled":
                    job.message = "in control.txt, line {}".format(job.line)
                continue
            if self.share.dat(job.day, job.file).exists():
                job.on_scanner = False
                job.measured = time.time()
                if job.discard:
                    self.log("job.discarded", "measured, data discarded (the job was cancelled)", job=job)
                else:
                    self.spawn(job, self.process(job))
            elif job.state == "measuring" and self.share.dat_in_transfer(job.day, job.file):
                job.message = "measured, the .seq.dat is being copied"

    def scanner_restarted(self, status: ScannerStatus) -> None:
        """`sync.bat` started again with a fresh `control.txt`: what was dropped
        but not read is no longer scheduled."""
        self.log("sync_bat.restarted", "sync.bat restarted: control.txt is new", level="warning")
        for job in self.jobs.values():
            if job.on_scanner and not job.read and not self.share.in_inbox(job.file) and status.find(job.file) is None:
                job.on_scanner = False
                if job.state == "scheduled":
                    job.priority = True
                    self.set(job, "ready", "sync.bat restarted before it was measured: scheduled again")

    async def process(self, job: Job) -> None:
        """Convert the `.seq.dat` and upload the signal."""
        self.set(job, "converting", "reading " + job.file + ".dat")
        partial = await asyncio.to_thread(self._convert, job)
        if job.state != "converting":
            return  # cancelled meanwhile
        if partial is not None:
            k, total = partial
            job.by = "supervisor"
            job.reason = job.reason or "aborted on the scanner after {} of {} ADCs".format(k, total)
            self.set(job, "cancelled", "the partial signal stays at the site: " + job.npy)
            return
        await self.upload(job)

    def _convert(self, job: Job) -> tuple[int, int] | None:
        """Write the job's signal next to its `.seq.dat`. Returns `(ADCs
        measured, ADCs in the sequence)` if the measurement was aborted."""
        counts = adc_sample_counts(self.seq_path(job).read_text(encoding="utf-8", errors="replace"))
        dat = self.share.dat(job.day, job.file)
        samples = read_dat(dat)
        partial = None
        if len(samples) != expected_lines(counts, self.coils, self.padding):
            k = whole_adcs(len(samples), counts, self.coils, self.padding)
            if k is None:
                convert(samples, counts, self.coils, self.padding)  # raises with the details
            partial, counts = (k, len(counts)), counts[:k]
        signal = convert(samples, counts, self.coils, self.padding)
        del samples
        if CONJUGATE:
            np.conjugate(signal, out=signal)
        npy = dat.with_name(job.file + ".signal.npy")
        tmp = npy.with_name(npy.name + ".tmp")
        with open(tmp, "wb") as f:
            np.save(f, signal, allow_pickle=False)
        os.replace(tmp, npy)
        job.npy, job.shape, job.partial = str(npy), list(signal.shape), partial is not None
        return partial

    async def upload(self, job: Job) -> None:
        self.set(job, "uploading", "signal {} x {} coils".format(*job.shape))
        job.progress, job.rate = 0.0, 0.0
        started = time.monotonic()

        def progress(done: int, total: int) -> None:
            job.progress = done / total if total else 1.0
            job.rate = done / max(time.monotonic() - started, 1e-3)

        await self.gateway.upload(job, Path(job.npy), progress)
        self.set(job, "done", "signal {} x {} coils uploaded ({}/s)".format(job.shape[0], job.shape[1], size(job.rate)))

    # --- what the operator and the agent can do -------------------------------

    def cancel(self, job: Job, by: str, reason: str = "") -> str:
        """Cancel `job` as far as it still goes. Returns what that means.
        Without a `reason` (the operator never types one), it says who did it."""
        if job.state in FINAL:
            return "{} is already {}".format(job.name, job.state)
        task = self.tasks.pop(job.id, None)
        if task is not None:
            task.cancel()
        if job.state == "uploading":
            self.spawn_quiet(self.gateway.abort_upload(job))
        note = "cancelled"
        if job.on_scanner:
            if not job.read and self.share.withdraw(job.file):
                job.on_scanner = False
                note = "cancelled, taken out of the inbox"
            else:
                job.discard = True
                note = "cancelled, but it is on the scanner: it is measured unless stopped there, and the data is discarded"
        job.by = by
        job.reason = reason or CANCEL_REASONS.get(by, "cancelled by " + by)
        self.set(job, "cancelled", note)
        return note

    def stays_on_scanner(self, job: Job) -> bool:
        """Whether a cancel would still let the scanner measure `job`."""
        return job.on_scanner and (job.read or not self.share.in_inbox(job.file))

    def spawn_quiet(self, coro) -> None:
        async def run() -> None:
            try:
                await coro
            except Exception as e:  # noqa: BLE001
                self.log("gateway.error", str(e), level="warning")

        asyncio.get_running_loop().create_task(run())

    def can_retry(self, job: Job | None) -> tuple[bool, bool]:
        """Whether `job` can be uploaded again, and measured again."""
        if job is None or job.state not in ("cancelled", "failed", "expired"):
            return False, False
        return self.has_data(job), self.seq_path(job).exists()

    async def retry(self, job: Job, mode: str = "auto", priority: bool = True) -> Job:
        """A new job for `job`: its signal uploaded again, or measured again."""
        upload, measure = self.can_retry(job)
        if mode == "auto":
            mode = "upload" if upload else "measure"
        if not (upload if mode == "upload" else measure):
            raise ScanError("{} cannot be {}".format(job.name, "uploaded again" if mode == "upload" else "measured again"))
        info = await self.gateway.retry(job, mode)
        new = self.add(info, retry_of=job.id, priority=priority)
        shutil.copyfile(self.seq_path(job), self.seq_path(new))
        new.duration = job.duration
        self.log("job.retry", "{} again as job {}".format("uploading" if mode == "upload" else "measuring", new.id), job=job)
        if mode == "upload":
            new.npy, new.shape, new.file, new.day = job.npy, job.shape, job.file, job.day
            self.spawn(new, self.upload(new))
        else:
            self.set(new, "ready", "restart of " + job.id)
        return new

    def seq_path(self, job: Job) -> Path:
        return self.seq_dir / (job.id + ".seq")

    # --- restart safety ---------------------------------------------------------

    def save(self) -> None:
        try:
            write_atomic(self.state_file, json.dumps({"jobs": [asdict(job) for job in self.jobs.values()]}).encode())
        except OSError:
            pass

    def load(self) -> None:
        try:
            data = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            return
        known = {f.name for f in fields(Job)}
        for entry in data.get("jobs", []):
            job = Job(**{k: v for k, v in entry.items() if k in known})
            self.jobs[job.id] = job

    def resume(self) -> None:
        """Carry on with what a previous run left unfinished. Needs the loop."""
        for job in self.jobs.values():
            if job.state == "downloading" or (job.state == "ready" and not self.seq_path(job).exists()):
                self.spawn(job, self.download(job))
            elif job.state == "converting":
                self.spawn(job, self.process(job))
            elif job.state == "uploading":
                self.spawn(job, self.upload(job))


# =============================================================================
# The TUI
# =============================================================================

STATE_STYLE = {
    "downloading": "dim",
    "ready": "",
    "scheduled": "blue",
    "measuring": "bold yellow",
    "converting": "magenta",
    "uploading": "cyan",
    "done": "green",
    "cancelled": "dark_orange",
    "failed": "bold red",
    "expired": "dim",
}
LEVEL_STYLE = {"info": "", "warning": "yellow", "error": "bold red"}


class ConfirmScreen(ModalScreen[bool]):
    """Asks yes or no. Enter or y confirms, Escape or n does not."""

    BINDINGS = [
        Binding("y", "answer(True)", "Yes"),
        Binding("n,escape", "answer(False)", "No"),
    ]

    def __init__(self, question: str, yes: str = "Yes") -> None:
        super().__init__()
        self.question = question
        self.yes = yes

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.question)
            with Horizontal(id="dialog-buttons"):
                yield Button(self.yes, variant="error", id="yes", compact=True)
                yield Button("No", id="no", compact=True)

    def on_mount(self) -> None:
        self.query_one("#yes", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "yes")

    def action_answer(self, yes: bool) -> None:
        self.dismiss(yes)


class ScannerApp(App):
    TITLE = "mrx scanner"
    CSS = """
    #info { height: auto; padding: 0 1; background: $boost; }
    #main { height: 1fr; }
    #jobs { width: 2fr; border: round $primary; }
    #side { width: 3fr; }
    #activity { height: 1fr; border: round $secondary; padding: 0 1; }
    #details { height: auto; border: round $secondary; padding: 0 1; }
    #actions { height: auto; margin-bottom: 1; }
    #actions Button { margin-right: 2; }
    #log { height: 10; border: round $secondary; }
    ConfirmScreen { align: center middle; }
    #dialog { width: 70; height: auto; border: thick $primary; background: $surface; padding: 1 2; }
    #dialog-buttons { height: auto; margin-top: 1; }
    #dialog-buttons Button { margin-right: 2; }
    """
    BINDINGS = [
        Binding("c", "cancel", "Cancel"),
        Binding("u", "retry('upload')", "Retry upload"),
        Binding("m", "retry('measure')", "Re-measure"),
        Binding("f", "toggle_finished", "Hide finished"),
        Binding("t", "copy_token", "Copy token"),
        Binding("a", "sim_abort", "Sim: abort"),
        Binding("s", "sim_restart", "Sim: restart sync.bat"),
        Binding("n", "demo_job", "Demo: new job"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, engine: Engine, settings: dict) -> None:
        super().__init__()
        self.engine = engine
        self.settings = settings
        self.selected: str | None = None
        self.hide_finished = False
        self._rows: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Static(id="info")
        with Horizontal(id="main"):
            yield DataTable(id="jobs", cursor_type="row", zebra_stripes=True)
            with Vertical(id="side"):
                yield Static(id="activity")
                with Vertical(id="details"):
                    with Horizontal(id="actions"):
                        yield Button("Cancel", id="cancel", variant="error", compact=True)
                        yield Button("Retry upload", id="retry-upload", compact=True)
                        yield Button("Re-measure", id="retry-measure", compact=True)
                    yield Static(id="detail")
        yield RichLog(id="log", markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#jobs", DataTable)
        table.border_title = "Jobs"
        for label, key in (("created", "created"), ("from", "from"), ("name", "name"), ("state", "state"), ("", "message")):
            table.add_column(label, key=key)
        self.query_one("#activity").border_title = "Activity"
        self.query_one("#details").border_title = "Details"
        self.query_one("#log").border_title = "Log"
        self.engine.log.listeners.append(self.on_log)
        self.engine.resume()
        self.set_interval(0.5, self.tick)
        self.refresh_views()

    async def tick(self) -> None:
        await self.engine.tick()
        self.refresh_views()

    def on_log(self, record: dict) -> None:
        line = Text(record["ts"][11:19] + " ", style="dim")
        if record.get("name"):
            line.append(record["name"] + " ", style="bold")
        line.append(record["message"], style=LEVEL_STYLE.get(record["level"], ""))
        self.query_one("#log", RichLog).write(line)

    # --- views -----------------------------------------------------------------

    def job(self) -> Job | None:
        return self.engine.jobs.get(self.selected) if self.selected else None

    def refresh_views(self) -> None:
        self.refresh_info()
        self.refresh_table()
        self.refresh_activity()
        self.refresh_details()
        self.refresh_bindings()

    def refresh_info(self) -> None:
        e, s = self.engine, self.settings
        info = Text()
        info.append(" {} ".format(s["mode"]), style="bold reverse " + ("green" if s["mode"] == "LIVE" else "yellow"))
        info.append("  {} · gateway ".format(OPERATOR if not OPERATOR.startswith("__") else "no session"))
        info.append(*{True: ("online", "green"), False: ("offline", "bold red"), None: ("…", "dim")}[e.gateway_online])
        info.append(" · sync.bat ")
        info.append(*(("running", "green") if e.sync_bat_alive else ("not running", "bold red")))
        info.append(" · {} · {} coils, padding {} · lookahead {} · v{}".format(s["share"], e.coils, e.padding, e.lookahead, VERSION))
        if e.latest_version != VERSION:
            info.append("  new script version {}: download it again".format(e.latest_version), style="bold yellow")
        if e.ended:
            info.append("\nSESSION ENDED: {} - get a new script at anyfield.net/scanner".format(e.ended), style="bold red")
        info.append("\nscan token ")
        info.append(SCAN_TOKEN, style="bold cyan")
        info.append("  (t copies it)", style="dim")
        self.query_one("#info", Static).update(info)

    def visible(self) -> list[Job]:
        jobs = sorted(self.engine.jobs.values(), key=lambda job: job.created)
        if self.hide_finished:
            jobs = [job for job in jobs if job.state not in FINAL or job.on_scanner]
        return jobs

    def refresh_table(self) -> None:
        table = self.query_one("#jobs", DataTable)
        jobs = self.visible()
        keys = {job.id for job in jobs}
        for key in self._rows - keys:
            table.remove_row(key)
        self._rows &= keys
        for job in jobs:
            state = Text(job.state, style=STATE_STYLE.get(job.state, ""))
            if job.state == "cancelled" and job.on_scanner:
                state.append(" (on scanner)", style="dim")
            # The whole message is in the details; here it must not widen the table
            short = job.message if len(job.message) <= 28 else job.message[:27] + "…"
            message = Text(short, style="dim")
            if job.id not in self._rows:
                created = datetime.fromtimestamp(job.created).strftime("%H:%M:%S")
                table.add_row(created, job.login, job.name, state, message, key=job.id)
                self._rows.add(job.id)
            else:
                table.update_cell(job.id, "state", state, update_width=True)
                table.update_cell(job.id, "message", message, update_width=True)
        if self.selected not in keys:
            self.selected = jobs[0].id if jobs else None

    def refresh_activity(self) -> None:
        grid = Table.grid(padding=(0, 1), expand=True)
        grid.add_column(width=11)
        grid.add_column(ratio=1)
        grid.add_column(width=18, justify="right")
        now = time.time()
        rows = 0
        for job in sorted(self.engine.jobs.values(), key=lambda job: job.created):
            if job.state == "downloading":
                grid.add_row(Text("download", style="dim"), job.name, "")
            elif job.state == "measuring":
                elapsed = now - job.measuring_since
                timing = "{} / ~{}".format(clock(elapsed), clock(job.duration)) if job.duration else clock(elapsed)
                grid.add_row(Text("measuring", style="bold yellow"), job.name, timing)
                if job.duration:
                    grid.add_row("", ProgressBar(total=job.duration, completed=min(elapsed, job.duration)), "")
            elif job.state == "converting":
                grid.add_row(Text("converting", style="magenta"), job.name, "")
            elif job.state == "uploading":
                grid.add_row(Text("uploading", style="cyan"), job.name, "{:3.0f}%  {}/s".format(job.progress * 100, size(job.rate)))
                grid.add_row("", ProgressBar(total=1.0, completed=job.progress), "")
            else:
                continue
            rows += 1
        ready = sum(1 for job in self.engine.jobs.values() if job.state == "ready")
        if ready:
            grid.add_row(Text("waiting", style="dim"), "{} job{} ready".format(ready, "s" if ready > 1 else ""), "")
            rows += 1
        self.query_one("#activity", Static).update(grid if rows else Text("idle", style="dim"))

    def refresh_details(self) -> None:
        job = self.job()
        detail = self.query_one("#detail", Static)
        if job is None:
            detail.update(Text("no job selected", style="dim"))
        else:
            text = Text()
            text.append(job.name, style="bold")
            text.append("  job {} · from {}\n".format(job.id, job.login))
            text.append(job.state, style=STATE_STYLE.get(job.state, ""))
            if job.by:
                text.append(" by " + job.by)
            if job.message:
                text.append(" - " + job.message)
            text.append("\n")
            if job.reason:
                text.append("reason: {}\n".format(job.reason))
            if job.retry_of:
                text.append("restart of job {}\n".format(job.retry_of))
            if job.file:
                text.append("file: {}{}\n".format(job.file, ", line {}".format(job.line) if job.line else ""), style="dim")
            if job.shape:
                text.append("signal: {} x {} coils{}\n".format(job.shape[0], job.shape[1], " (partial)" if job.partial else ""), style="dim")
            if job.duration:
                text.append("expected duration: {}\n".format(clock(job.duration)), style="dim")
            detail.update(text)
        upload, measure = self.engine.can_retry(job)
        self.query_one("#cancel", Button).disabled = job is None or job.state in FINAL
        self.query_one("#retry-upload", Button).disabled = not upload
        self.query_one("#retry-measure", Button).disabled = not measure

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action in ("sim_abort", "sim_restart"):
            return self.engine.scanner is not None
        if action == "demo_job":
            return isinstance(self.engine.gateway, DemoGateway)
        job = self.job()
        if action == "cancel":
            return None if job is None or job.state in FINAL else True
        if action == "retry":
            upload, measure = self.engine.can_retry(job)
            return True if (upload if parameters and parameters[0] == "upload" else measure) else None
        return True

    # --- events and actions ----------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value is not None:
            self.selected = event.row_key.value
            self.refresh_details()
            self.refresh_bindings()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = {
            "cancel": "cancel",
            "retry-upload": "retry('upload')",
            "retry-measure": "retry('measure')",
        }.get(event.button.id or "")
        if action:
            await self.run_action(action)

    def action_cancel(self) -> None:
        job = self.job()
        if job is None or job.state in FINAL:
            return
        question = "Cancel {} (job {} from {})?".format(job.name, job.id, job.login)
        if self.engine.stays_on_scanner(job):
            question += "\n\nIt is already on the scanner: it is still measured unless you stop it there, and its data is discarded."

        def done(yes: bool | None) -> None:
            if yes and job.state not in FINAL:
                note = self.engine.cancel(job, "operator")
                self.notify(note, severity="warning" if "on the scanner" in note else "information")
                self.refresh_views()

        self.push_screen(ConfirmScreen(question, yes="Cancel job"), done)

    async def action_retry(self, mode: str) -> None:
        job = self.job()
        if job is None:
            return
        try:
            new = await self.engine.retry(job, mode, priority=True)
        except Exception as e:  # noqa: BLE001 - shown to the operator
            self.notify(str(e), severity="error")
            return
        self.selected = new.id
        self.refresh_views()

    def action_toggle_finished(self) -> None:
        self.hide_finished = not self.hide_finished
        self.refresh_views()

    def action_copy_token(self) -> None:
        self.copy_to_clipboard(SCAN_TOKEN)
        self.notify("scan token copied")

    def action_sim_abort(self) -> None:
        if self.engine.scanner is not None and self.engine.scanner.abort():
            self.notify("simulated: the supervisor stopped the measurement")

    def action_sim_restart(self) -> None:
        if self.engine.scanner is not None:
            self.engine.scanner.restart()
            self.notify("simulated: sync.bat restarted")

    def action_demo_job(self) -> None:
        if isinstance(self.engine.gateway, DemoGateway):
            self.engine.gateway.first += 1
            self.engine._next_sync = 0


# =============================================================================
# Main
# =============================================================================


def settings(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measures the sequences queued on this scanner session.")
    parser.add_argument("--share", help="the scanner share as this PC sees it (default {})".format(DEFAULT_SHARE))
    parser.add_argument("--coils", type=int, default=DEFAULT_COILS, help="receive coils (default %(default)s)")
    parser.add_argument("--adc-padding", type=int, default=DEFAULT_ADC_PADDING, help="extra samples per coil readout (default %(default)s)")
    parser.add_argument("--lookahead", type=int, default=1, help="jobs kept scheduled behind the measurement in progress (default %(default)s)")
    parser.add_argument("--workdir", help="where downloaded sequences and the state file go (default: next to this script)")
    parser.add_argument("--simulate", action="store_true", help="no scanner: play sync.bat and the scanner on a local folder, the data is noise")
    parser.add_argument("--demo", action="store_true", help="no gateway either: made-up jobs (implies --simulate)")
    parser.add_argument("--sim-duration", type=float, help="seconds every simulated measurement takes (default: the sequence's TotalDuration)")
    args = parser.parse_args(argv)
    if args.demo:
        args.simulate = True
    return args


def main(argv: list[str] | None = None) -> int:
    args = settings(argv)
    if not args.demo and not RUNNER_SECRET.startswith("scr_"):
        print("This is the template. Download your own script at https://anyfield.net/scanner/ - or try it with --demo.")
        return 2

    workdir = Path(args.workdir) if args.workdir else SCRIPT_DIR / "mrx_scanner_data"
    if args.demo:
        workdir = workdir / "demo"
        shutil.rmtree(workdir, ignore_errors=True)  # every demo starts empty
    workdir.mkdir(parents=True, exist_ok=True)
    share = Share(Path(args.share) if args.share else (workdir / "share" if args.simulate else Path(DEFAULT_SHARE)))
    scanner = SimulatedScanner(share, args.coils, args.adc_padding, args.sim_duration) if args.simulate else None
    problems = share.check()
    if problems:
        print("\n".join(problems))
        return 1

    log = EventLog(workdir if args.demo else SCRIPT_DIR)
    gateway = DemoGateway() if args.demo else HttpGateway(BASE_URL, RUNNER_SECRET)
    engine = Engine(gateway, share, workdir, log, args.coils, args.adc_padding, args.lookahead, scanner)
    mode = "DEMO" if args.demo else "SIMULATION" if args.simulate else "LIVE"
    log("script.start", "started ({}), share {}".format(mode.lower(), share.root), version=VERSION)
    ScannerApp(engine, {"mode": mode, "share": str(share.root)}).run()
    log("script.stop", "stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
