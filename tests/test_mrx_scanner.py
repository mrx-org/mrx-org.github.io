"""Tests for docs/scanner/mrx_scanner.py.

    uv run --with pytest --with textual --with numpy --with httpx pytest tests

The engine runs against the simulated scanner (sync.bat, interpreter and ICE
program on a temporary folder) and the demo gateway, with measurements of a few
hundredths of a second.
"""

import asyncio
import importlib.util
import random
import sys
import time
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "docs" / "scanner" / "mrx_scanner.py"
spec = importlib.util.spec_from_file_location("mrx_scanner", SCRIPT)
ms = importlib.util.module_from_spec(spec)
sys.modules["mrx_scanner"] = ms
spec.loader.exec_module(ms)

COILS = 2


def make(tmp_path, jobs=0, duration=0.05, lookahead=1):
    share = ms.Share(tmp_path / "share")
    scanner = ms.SimulatedScanner(share, duration, COILS)
    gateway = ms.DemoGateway(first=jobs, every=None, rng=random.Random(1))

    async def download(job):
        return ms.demo_seq(6, 16, duration).encode()

    async def upload(job, path, progress):
        progress(path.stat().st_size, path.stat().st_size)

    gateway.download, gateway.upload = download, upload
    log = ms.EventLog(tmp_path / "logs")
    engine = ms.Engine(gateway, share, tmp_path / "work", log, lookahead, scanner)
    return engine, gateway, scanner


async def run_until(engine, condition, timeout=10.0):
    end = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > end:
            states = {job.name: job.state for job in engine.jobs.values()}
            raise AssertionError("timed out, jobs: {}".format(states))
        engine._next_sync = 0  # no waiting for the sync interval in tests
        await engine.tick()
        await asyncio.sleep(0.01)


def states(engine):
    return [job.state for job in sorted(engine.jobs.values(), key=lambda job: job.created)]


# --- pure functions -----------------------------------------------------------


def test_demo_seq_is_read_back():
    text = ms.demo_seq(5, 32, 7.5)
    assert ms.adc_sample_counts(text) == [32] * 5
    assert ms.seq_duration(text) == 7.5


def test_name_in_file():
    assert ms.name_in_file("gre_2d.seq", "abc") == "gre_2d"
    assert ms.name_in_file("T1 map (Müller) 50%!.SEQ", "abc") == "T1_map_Muller_50"
    assert ms.name_in_file(r"..\a/b:c*?.seq", "abc") == "a_b_c"
    assert ms.name_in_file("x" * 100, "abc") == "x" * ms.NAME_IN_FILE
    assert ms.name_in_file("abc", "abc") == ""  # the job id standing in for a name
    assert ms.name_in_file("%!&^", "abc") == ""


def test_whole_adcs():
    counts = [10, 20, 30]
    assert ms.whole_adcs(0, counts) == 0
    assert ms.whole_adcs(9, counts) == 0
    assert ms.whole_adcs(10, counts) == 1
    assert ms.whole_adcs(29, counts) == 1  # cut in the middle of the 2nd ADC
    assert ms.whole_adcs(60, counts) == 3


def test_read_and_check_done(tmp_path):
    path = tmp_path / "a.seq.done"
    assert ms.read_done(path) is None
    path.write_text("format 1\n")  # still being copied
    assert ms.read_done(path) is None
    path.write_text("format 1\nstatus complete   # comment\nscans 3\nskipped_scans 0\n")
    done = ms.read_done(path)
    assert done["status"] == "complete" and done["scans"] == "3"
    assert ms.check_done(done, "a.seq") == "complete"
    assert ms.check_done({**done, "status": "aborted"}, "a.seq") == "aborted"
    for bad, words in (
        ({"format": "2"}, "format 2"),
        ({"status": "empty"}, "no ADCs"),
        ({"status": "failed"}, "failed"),
        ({"status": "odd"}, "unknown"),
        ({"skipped_scans": "4"}, "4 scans"),
    ):
        with pytest.raises(ms.ScanError, match=words):
            ms.check_done({**done, **bad}, "a.seq")


def test_fake_result_has_the_scanner_layout(tmp_path):
    seq = tmp_path / "a.seq"
    ms.write_fake_result(seq, [16, 32], 3, "aborted", rows=20)
    signal = np.load(tmp_path / "a.seq.npy")
    scans = np.load(tmp_path / "a.seq.scans.npy")
    assert signal.shape == (20, 3) and signal.dtype == np.complex64
    assert scans.dtype == ms.SCANS_DTYPE and scans.dtype.itemsize == 42  # packed
    assert list(scans["offset"]) == [0, 16] and list(scans["n"]) == [16, 4]
    assert ms.read_done(tmp_path / "a.seq.done")["status"] == "aborted"
    ms.write_fake_result(tmp_path / "b.seq", [], 3)
    assert not (tmp_path / "b.seq.npy").exists()
    assert ms.read_done(tmp_path / "b.seq.done")["status"] == "empty"


def test_status_finds_lines_and_dates():
    status = ms.ScannerStatus("run", 1, "20261119", [r"C:\x\20261118\a.seq", "", r"C:\x\20261119\b.seq", "wait"], 1)
    assert status.find("a.seq") == (1, "20261118")
    assert status.find("b.seq") == (3, "20261119")
    assert status.find("c.seq") is None


def test_share_status_missing_is_none(tmp_path):
    assert ms.Share(tmp_path).read_status() is None


# --- the pipeline -------------------------------------------------------------


def test_jobs_run_through_in_order(tmp_path):
    engine, _, _ = make(tmp_path, jobs=3)

    async def go():
        await run_until(engine, lambda: len(engine.jobs) == 3 and all(s == "done" for s in states(engine)))

    asyncio.run(go())
    jobs = sorted(engine.jobs.values(), key=lambda job: job.created)
    assert [job.line for job in jobs] == [1, 2, 3]
    # The name order is the drop order; the job's name is in it, the id last
    assert [job.file for job in jobs] == sorted(job.file for job in jobs)
    assert all(job.file.endswith("_{}_{}.seq".format(job.name, job.id)) for job in jobs)
    for job in jobs:
        signal = np.load(job.npy)
        assert signal.shape == (6 * 16, COILS)
        assert signal.dtype == np.complex64
        measured = np.load(ms.Share(tmp_path / "share").result(job.day, job.file, ".npy"))
        assert np.array_equal(signal, measured.conj() if ms.CONJUGATE else measured)
    log = (tmp_path / "logs").glob("scan-log-*.jsonl")
    assert any("job.done" in path.read_text() for path in log)


def test_lookahead_keeps_one_job_ahead(tmp_path):
    engine, _, scanner = make(tmp_path, jobs=4, duration=0.5)

    async def go():
        await run_until(engine, lambda: "measuring" in states(engine) and len(scanner.lines) == 2)
        for _ in range(5):  # and it stays that way while the measurement runs
            await engine.tick()
        assert states(engine).count("scheduled") == 1
        assert states(engine).count("ready") == 2
        assert len(scanner.lines) == 2  # the one measured and the one behind it

    asyncio.run(go())


def test_cancel_ready_job_never_reaches_the_scanner(tmp_path):
    engine, _, scanner = make(tmp_path, jobs=3, duration=0.3)

    async def go():
        await run_until(engine, lambda: states(engine).count("ready") == 1 and "measuring" in states(engine))
        ready = next(job for job in engine.jobs.values() if job.state == "ready")
        assert engine.cancel(ready, "operator", "not needed") == "cancelled"
        await run_until(engine, lambda: all(s in ms.FINAL for s in states(engine)))
        assert ready.state == "cancelled" and ready.by == "operator" and ready.reason == "not needed"
        assert not any(ready.id in line for line in scanner.lines)

    asyncio.run(go())


def test_cancel_on_scanner_measures_and_discards(tmp_path):
    engine, gateway, scanner = make(tmp_path, jobs=2, duration=0.3)

    async def go():
        await run_until(engine, lambda: "measuring" in states(engine))
        job = next(job for job in engine.jobs.values() if job.state == "measuring")
        gateway.request_cancel(job.id, "wrong FOV")
        await run_until(engine, lambda: job.state == "cancelled")
        assert job.by == "agent" and job.discard
        await run_until(engine, lambda: not job.on_scanner)  # measured anyway
        await run_until(engine, lambda: all(s in ms.FINAL for s in states(engine)))
        assert not job.npy  # nothing converted
        assert states(engine).count("done") == 1

    asyncio.run(go())


def test_abort_on_scanner_is_detected(tmp_path):
    engine, _, scanner = make(tmp_path, jobs=1, duration=30)

    async def go():
        await run_until(engine, lambda: states(engine) == ["measuring"])
        assert scanner.abort()
        await run_until(engine, lambda: states(engine) == ["cancelled"])

    asyncio.run(go())
    job = next(iter(engine.jobs.values()))
    assert job.by == "supervisor"
    assert "3 of 6 ADCs" in job.reason
    assert job.partial and np.load(job.npy).shape == (3 * 16, COILS)
    assert engine.can_retry(job) == (False, True)  # partial data: measure again only


def test_scanner_errors_fail_the_job(tmp_path, monkeypatch):
    engine, _, _ = make(tmp_path, jobs=3)
    outcomes = iter([("empty", None), ("failed", None), ("complete", 10)])  # the last one: rows missing

    def fake(seq, counts, coils, status="complete", rows=None, rng=None):
        status, rows = next(outcomes)
        real(seq, counts if status != "empty" else [], coils, status, rows)

    real = ms.write_fake_result
    monkeypatch.setattr(ms, "write_fake_result", fake)
    asyncio.run(run_until(engine, lambda: len(engine.jobs) == 3 and all(s in ms.FINAL for s in states(engine))))
    jobs = sorted(engine.jobs.values(), key=lambda job: job.created)
    assert [job.state for job in jobs] == ["failed"] * 3
    assert "no ADCs" in jobs[0].message
    assert "status failed" in jobs[1].message
    assert "10 rows" in jobs[2].message and "96 samples" in jobs[2].message


def test_read_error(tmp_path):
    path = tmp_path / "a.seq.error"
    assert ms.read_error(path) is None
    path.write_text("load_failed: unknown section [FOO]\r\n")
    assert ms.read_error(path) == "the interpreter could not load the sequence: unknown section [FOO]"
    path.write_text("handover_failed: access denied\n")
    assert ms.read_error(path).startswith("the sequence could not be handed over")
    path.write_text("something else\n")
    assert ms.read_error(path) == "the scanner did not measure it: something else"


def test_sequence_that_does_not_load_fails_with_the_error(tmp_path):
    engine, gateway, _ = make(tmp_path, jobs=2)
    good = gateway.download
    seqs = iter([b"[BLOCKS]\n1 100 0 0 0 0 7 0\n", None])  # ADC 7 is not defined

    async def download(job):
        return next(seqs) or await good(job)

    gateway.download = download
    asyncio.run(run_until(engine, lambda: len(engine.jobs) == 2 and all(s in ms.FINAL for s in states(engine))))
    first, second = sorted(engine.jobs.values(), key=lambda job: job.created)
    assert first.state == "failed" and first.message.startswith("the interpreter could not load the sequence")
    assert "no ADCs" not in first.message  # the empty .done after it is not read
    assert second.state == "done"


def test_job_without_data_is_failed_once_a_later_one_has_data(tmp_path, monkeypatch):
    engine, _, _ = make(tmp_path, jobs=2)
    monkeypatch.setattr(ms, "LOST_AFTER", 0.1)
    calls = []

    def fake(seq, *args, **kwargs):
        calls.append(seq)
        if len(calls) > 1:  # the first one leaves nothing: the sequence gave up
            real(seq, *args, **kwargs)

    real = ms.write_fake_result
    monkeypatch.setattr(ms, "write_fake_result", fake)
    asyncio.run(run_until(engine, lambda: len(engine.jobs) == 2 and all(s in ms.FINAL for s in states(engine))))
    first, second = sorted(engine.jobs.values(), key=lambda job: job.created)
    assert second.state == "done"
    assert first.state == "failed" and "gave up" in first.message and not first.on_scanner


def test_retry_measure_and_upload(tmp_path):
    engine, _, _ = make(tmp_path, jobs=1)

    async def go():
        await run_until(engine, lambda: states(engine) == ["done"])
        job = next(iter(engine.jobs.values()))
        engine.set(job, "failed", "pretend the upload failed")
        assert engine.can_retry(job) == (True, True)
        again = await engine.retry(job, "upload")
        await run_until(engine, lambda: again.state == "done")
        assert again.retry_of == job.id and again.npy == job.npy
        measured = await engine.retry(job, "measure")
        await run_until(engine, lambda: measured.state == "done")
        assert measured.npy != job.npy

    asyncio.run(go())


def test_sync_bat_restart_schedules_again(tmp_path):
    engine, _, scanner = make(tmp_path, jobs=2, duration=1.0)

    async def go():
        await run_until(engine, lambda: "measuring" in states(engine) and "scheduled" in states(engine))
        scheduled = next(job for job in engine.jobs.values() if job.state == "scheduled")
        await run_until(engine, lambda: scheduled.line > 0)  # in control.txt
        scanner.restart()
        await run_until(engine, lambda: scheduled.state != "scheduled" or scheduled.line == 1)
        await run_until(engine, lambda: all(s == "done" for s in states(engine)), timeout=15)

    asyncio.run(go())


def test_sync_bat_offline_is_noticed(tmp_path, monkeypatch):
    engine, _, _ = make(tmp_path)
    monkeypatch.setattr(ms, "SYNC_BAT_TIMEOUT", 0.2)

    async def go():
        await run_until(engine, lambda: engine.sync_bat_alive)
        engine.scanner = None  # sync.bat stops
        await run_until(engine, lambda: not engine.sync_bat_alive)

    asyncio.run(go())


def test_state_survives_a_restart(tmp_path):
    engine, _, _ = make(tmp_path, jobs=1)
    asyncio.run(run_until(engine, lambda: states(engine) == ["done"]))
    again, _, _ = make(tmp_path)
    assert states(again) == ["done"]


# --- the TUI ------------------------------------------------------------------


def test_tui_shows_jobs_and_cancels(tmp_path):
    engine, _, _ = make(tmp_path, jobs=3, duration=5)

    async def go():
        app = ms.ScannerApp(engine, {"mode": "DEMO", "share": "test"})
        async with app.run_test() as pilot:
            for _ in range(100):
                await pilot.pause(0.05)
                if "measuring" in states(engine) and "ready" in states(engine):
                    break
            table = app.query_one("#jobs")
            assert table.row_count == 3
            ready = next(job for job in engine.jobs.values() if job.state == "ready")
            app.selected = ready.id
            await pilot.press("c")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert ready.state == "cancelled" and ready.by == "operator"
            assert ready.reason == ms.CANCEL_REASONS["operator"]  # never typed in
            await pilot.press("f")  # hide finished
            await pilot.pause(0.6)
            assert table.row_count == 2

    asyncio.run(go())
