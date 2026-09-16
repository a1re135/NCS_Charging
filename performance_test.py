"""L1 capacity/performance test harness for NCS Charging.

The benchmark uses the teacher's L1 target QPS as the offered load. In --stages
mode it runs 25%, 50%, 75%, 100% and 125% of each target rate. This is more
meaningful than simply multiplying thread count because concurrency and QPS are
not the same thing.

Read-only mode is safe for the demo. Use --write-test only with
prepare_l1_loadtest.py --prepare and preferably against a test/staging database.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import requests

_CAP_SPEC = spec_from_file_location(
    "ncs_capacity_standalone", Path(__file__).with_name("ncs") / "capacity.py"
)
if _CAP_SPEC is None or _CAP_SPEC.loader is None:
    raise RuntimeError("Unable to load ncs/capacity.py")
_CAP = module_from_spec(_CAP_SPEC)
_CAP_SPEC.loader.exec_module(_CAP)
CAPACITY_LEVEL, get_capacity = _CAP.CAPACITY_LEVEL, _CAP.get_capacity
TARGETS = get_capacity()

USERS = [(f"18800000{i:03d}", "LoadTest123456") for i in range(1, 101)]
REQUEST_TIMEOUT = (5, 20)
HEALTH_TIMEOUT = (3, 5)
TRANSIENT_CODES = {502, 503, 504}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    x = sorted(values)
    k = (len(x) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return x[f] if f == c else x[f] + (x[c] - x[f]) * (k - f)


def login(
    session: requests.Session,
    base: str,
    phone: str,
    password: str,
) -> str:
    r = session.get(
        base + "/api/session",
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()

    token = r.json().get("csrf")

    if not token:
        raise RuntimeError(
            "Login preflight did not return CSRF token"
        )

    r = session.post(
        base + "/api/login",
        json={
            "phone": phone,
            "password": password,
        },
        headers={
            "X-CSRF-Token": token,
        },
        timeout=REQUEST_TIMEOUT,
    )

    r.raise_for_status()

    csrf = r.json().get("csrf")

    if not csrf:
        raise RuntimeError(
            "Login did not return CSRF token"
        )

    return csrf


def record_call(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 0,
    **kwargs,
):
    started = time.perf_counter()
    last_code = 0
    last_payload = None
    for attempt in range(retries + 1):
        try:
            response = session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
            last_code = response.status_code
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    last_payload = response.json()
                except ValueError:
                    last_payload = None
            if response.ok or response.status_code not in TRANSIENT_CODES or attempt >= retries:
                return (
                    response.ok,
                    (time.perf_counter() - started) * 1000,
                    last_code,
                    last_payload,
                )
        except requests.RequestException:
            if attempt >= retries:
                return False, (time.perf_counter() - started) * 1000, 0, None
        time.sleep(0.05 * (attempt + 1))
    return False, (time.perf_counter() - started) * 1000, last_code, last_payload


def health_check(base: str, retries: int = 8) -> tuple[bool, str]:
    """Check service health with retry/backoff so an overloaded stage does not crash the runner."""
    last_error = "unknown error"
    for attempt in range(retries):
        try:
            r = requests.get(base + "/api/health", timeout=HEALTH_TIMEOUT)
            if r.ok:
                payload = r.json()
                if payload.get("ok") is False:
                    last_error = "database health check failed"
                else:
                    return True, "ok"
            else:
                last_error = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(min(0.5 * (attempt + 1), 3.0))
    return False, last_error


def paced_worker(
    session: requests.Session,
    base: str,
    endpoint: str,
    duration: float,
    worker_id: int,
    target_qps: float,
    worker_count: int,
    start_event: threading.Event,
):
    # All worker sessions are already authenticated
    # before the measured benchmark begins.

    start_event.wait()

    started = time.perf_counter()
    deadline = started + duration

    interval = max(
        0.001,
        worker_count
        / max(
            target_qps,
            0.001,
        ),
    )

    next_at = (
        started
        + worker_id
        / max(
            target_qps,
            0.001,
        )
    )

    ok = 0
    err = 0
    lat = []
    codes = []

    while time.perf_counter() < deadline:
        sleep_for = (
            next_at
            - time.perf_counter()
        )

        if sleep_for > 0:
            time.sleep(
                min(
                    sleep_for,
                    max(
                        0.0,
                        deadline
                        - time.perf_counter(),
                    ),
                )
            )

        if time.perf_counter() >= deadline:
            break

        good, ms, code, _ = record_call(
            session,
            "GET",
            base + endpoint,
            retries=1,
        )

        lat.append(ms)
        codes.append(code)

        ok += int(good)
        err += int(not good)

        next_at += interval

    return {
        "ok": ok,
        "err": err,
        "lat": lat,
        "codes": codes,
        "login_error": 0,
    }


def login_worker(
    base: str,
    duration: float,
    worker_id: int,
    offered_qps: float,
    worker_count: int,
):
    deadline = (
        time.perf_counter()
        + duration
    )

    phone, password = USERS[
        worker_id % len(USERS)
    ]

    ok = 0
    err = 0

    lat = []
    codes = []

    # Divide total offered QPS across all workers.
    interval = max(
        0.001,
        worker_count
        / max(
            offered_qps,
            0.001,
        ),
    )

    next_at = (
        time.perf_counter()
        + worker_id
        / max(
            offered_qps,
            0.001,
        )
    )

    while (
        time.perf_counter()
        < deadline
    ):
        sleep_for = (
            next_at
            - time.perf_counter()
        )

        if sleep_for > 0:
            time.sleep(
                min(
                    sleep_for,
                    max(
                        0.0,
                        deadline
                        - time.perf_counter(),
                    ),
                )
            )

        if (
            time.perf_counter()
            >= deadline
        ):
            break

        session = (
            requests.Session()
        )

        started = (
            time.perf_counter()
        )

        try:
            pre = session.get(
                base + "/api/session",
                timeout=REQUEST_TIMEOUT,
            )

            token = (
                pre.json()
                .get("csrf")
            )

            if not token:
                raise RuntimeError(
                    "missing CSRF token"
                )

            response = session.post(
                base + "/api/login",
                json={
                    "phone":
                        phone,
                    "password":
                        password,
                },
                headers={
                    "X-CSRF-Token":
                        token,
                },
                timeout=REQUEST_TIMEOUT,
            )

            good = response.ok
            code = (
                response.status_code
            )

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ):
            good = False
            code = 0

        lat.append(
            (
                time.perf_counter()
                - started
            )
            * 1000
        )

        codes.append(code)

        ok += int(good)
        err += int(
            not good
        )

        next_at += interval

    return {
        "ok": ok,
        "err": err,
        "lat": lat,
        "codes": codes,
        "login_error": 0,
    }


def write_cycle_worker(
    session: requests.Session,
    csrf: str,
    base: str,
    duration: float,
    worker_id: int,
    offered_qps: float,
    worker_count: int,
    start_event: threading.Event,
):
    charger_id = (
        worker_id % 100
    ) + 1

    start_event.wait()

    started = time.perf_counter()
    deadline = started + duration

    interval = max(
        0.001,
        worker_count
        / max(
            offered_qps,
            0.001,
        ),
    )

    next_at = (
        started
        + worker_id
        / max(
            offered_qps,
            0.001,
        )
    )

    sc = 0
    fc = 0
    se = 0
    fe = 0

    start_lat = []
    finish_lat = []

    while (
        time.perf_counter()
        < deadline
    ):
        sleep_for = (
            next_at
            - time.perf_counter()
        )

        if sleep_for > 0:
            time.sleep(
                min(
                    sleep_for,
                    max(
                        0.0,
                        deadline
                        - time.perf_counter(),
                    ),
                )
            )

        if (
            time.perf_counter()
            >= deadline
        ):
            break

        # Refresh CSRF from the same authenticated
        # session before the write operation.
        try:
            session_data = session.get(
                base + "/api/session",
                timeout=REQUEST_TIMEOUT,
            ).json()

            current_csrf = (
                session_data.get("csrf")
                or csrf
            )

            good, ms, _code, start_payload = (
                record_call(
                    session,
                    "POST",
                    base + "/api/orders",
                    json={
                        "charger_id":
                            charger_id,

                        "mode":
                            "start",
                    },
                    headers={
                        "X-CSRF-Token":
                            current_csrf,
                    },
                )
            )

        except (
            requests.RequestException,
            ValueError,
            KeyError,
        ):
            good = False
            ms = 0.0
            start_payload = None

        start_lat.append(ms)

        sc += int(good)
        se += int(not good)

        if good:
            try:
                oid = int(
                    start_payload["id"]
                )

                session_data = (
                    session.get(
                        base + "/api/session",
                        timeout=
                            REQUEST_TIMEOUT,
                    ).json()
                )

                current_csrf = (
                    session_data.get(
                        "csrf"
                    )
                    or csrf
                )

                good2, ms2, _code2, _ = (
                    record_call(
                        session,
                        "POST",
                        (
                            base
                            + f"/api/orders/"
                              f"{oid}/finish"
                        ),
                        json={},
                        headers={
                            "X-CSRF-Token":
                                current_csrf,
                        },
                    )
                )

            except (
                requests.RequestException,
                ValueError,
                KeyError,
                TypeError,
            ):
                good2 = False
                ms2 = 0.0

            finish_lat.append(
                ms2
            )

            fc += int(good2)
            fe += int(not good2)

        next_at += interval

    return {
        "start": (
            sc,
            se,
            start_lat,
        ),
        "finish": (
            fc,
            fe,
            finish_lat,
        ),
    }

def agent_worker(
    base: str,
    duration: float,
    worker_id: int,
    offered_qps: float,
    worker_count: int,
):
    session = requests.Session()

    phone, password = USERS[
        worker_id % len(USERS)
    ]

    try:
        csrf = login(
            session,
            base,
            phone,
            password,
        )
    except (
        requests.RequestException,
        ValueError,
        RuntimeError,
    ):
        return {
            "ok": 0,
            "err": 1,
            "lat": [],
            "codes": [0],
            "fallbacks": 0,
            "login_error": 1,
        }

    deadline = (
        time.perf_counter()
        + duration
    )

    # Each worker contributes part of the total
    # offered QPS.
    interval = max(
        0.001,
        worker_count
        / max(
            offered_qps,
            0.001,
        ),
    )

    # Stagger requests so we do not send all
    # workers at exactly the same instant.
    next_at = (
        time.perf_counter()
        + worker_id
        / max(
            offered_qps,
            0.001,
        )
    )

    ok = 0
    err = 0
    fallbacks = 0

    lat = []
    codes = []

    while (
        time.perf_counter()
        < deadline
    ):
        sleep_for = (
            next_at
            - time.perf_counter()
        )

        if sleep_for > 0:
            time.sleep(
                min(
                    sleep_for,
                    max(
                        0.0,
                        deadline
                        - time.perf_counter(),
                    ),
                )
            )

        if (
            time.perf_counter()
            >= deadline
        ):
            break

        good, ms, code, payload = (
            record_call(
                session,
                "POST",
                base + "/api/agent/chat",
                json={
                    "message":
                        "我附近有没有地方可以快速给车充电？",

                    "lat":
                        39.9593,

                    "lng":
                        116.2981,
                },
                headers={
                    "X-CSRF-Token":
                        csrf,
                },
            )
        )

        # HTTP 200 alone is not enough.
        #
        # If GLM fails, our application intentionally
        # falls back to the local Agent and still
        # returns HTTP 200.
        #
        # For this benchmark we only count a request
        # as successful when the real GLM path ran.
        glm_ok = (
            good
            and isinstance(
                payload,
                dict,
            )
            and payload.get(
                "agent_mode"
            ) == "glm"
            and bool(
                payload.get(
                    "answer"
                )
            )
        )

        if (
            good
            and isinstance(
                payload,
                dict,
            )
            and payload.get(
                "agent_mode"
            ) != "glm"
        ):
            fallbacks += 1

        lat.append(ms)
        codes.append(code)

        ok += int(glm_ok)
        err += int(
            not glm_ok
        )

        next_at += interval

    return {
        "ok": ok,
        "err": err,
        "lat": lat,
        "codes": codes,
        "fallbacks": fallbacks,
        "login_error": 0,
    }

def aggregate(parts):
    ok = sum(x.get("ok", 0) for x in parts)
    err = sum(x.get("err", 0) for x in parts)
    lat = [m for x in parts for m in x.get("lat", [])]
    return ok, err, lat


def run_read_case(
    base: str,
    name: str,
    endpoint: str,
    target_qps: float,
    duration: float,
    workers: int,
):
    worker_count = max(
        1,
        min(
            workers,
            120,
        ),
    )

    # Authenticate all worker sessions BEFORE
    # starting the measured benchmark window.
    sessions = []

    for i in range(worker_count):
        session = requests.Session()

        phone, password = USERS[
            i % len(USERS)
        ]

        try:
            login(
                session,
                base,
                phone,
                password,
            )

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ):
            return {
                "name": name,
                "endpoint": endpoint,
                "requests": 1,
                "success": 0,
                "errors": 1,
                "error_rate": 1.0,
                "elapsed_seconds": 0,
                "qps": 0,
                "target_qps": target_qps,
                "avg_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "target_met": False,
            }

        sessions.append(session)

    start_event = (
        threading.Event()
    )

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as pool:

        futures = [
            pool.submit(
                paced_worker,
                sessions[i],
                base,
                endpoint,
                duration,
                i,
                target_qps,
                worker_count,
                start_event,
            )
            for i in range(
                worker_count
            )
        ]

        # Start every worker from the same
        # measurement boundary.
        started = (
            time.perf_counter()
        )

        start_event.set()

        parts = [
            future.result()
            for future
            in as_completed(
                futures
            )
        ]

    elapsed = max(
        time.perf_counter()
        - started,
        0.001,
    )

    ok, err, lat = aggregate(
        parts
    )

    total = ok + err

    actual_qps = (
        ok / elapsed
    )

    return {
        "name": name,
        "endpoint": endpoint,
        "requests": total,
        "success": ok,
        "errors": err,
        "error_rate":
            err / max(total, 1),
        "elapsed_seconds":
            elapsed,
        "qps": actual_qps,
        "target_qps":
            target_qps,
        "avg_ms":
            statistics.fmean(lat)
            if lat
            else 0,
        "p95_ms":
            percentile(lat, 95),
        "p99_ms":
            percentile(lat, 99),
        "target_met": (
            ok > 0
            and actual_qps
                >= target_qps
            and err == 0
        ),
    }


def bench_reads(
    base,
    duration,
    workers,
    scale=1.0,
):
    specs = [
        (
            "station_query",
            "/api/stations",
        ),
        (
            "device_view",
            "/api/stations/1",
        ),
    ]

    results = []

    for name, endpoint in specs:

        required_target = (
            TARGETS["qps"][name]
            * scale
        )

        offered_target = (
            required_target
            * 1.10
        )

        result = run_read_case(
            base,
            name,
            endpoint,
            offered_target,
            duration,
            workers,
        )

        # The benchmark offered 110%, but
        # acceptance is against the official
        # course requirement.
        result["offered_qps"] = (
            offered_target
        )

        result["target_qps"] = (
            required_target
        )

        result["target_met"] = (
            result["success"] > 0
            and result["qps"]
                >= required_target
            and result["errors"] == 0
        )

        results.append(
            result
        )

    return results


def bench_login(base, duration, workers, scale=1.0):
    required_target = (
        TARGETS["qps"]["login"]
        * scale
    )

    # Offer 10% above the required capacity.
    # Pass/fail is still judged against the real
    # course requirement, not the higher offered load.
    offered_target = (
        required_target
        * 1.10
    )
    worker_count = max(1, min(workers, 60))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [
            pool.submit(
                login_worker,
                base,
                duration,
                i,
                offered_target,
                worker_count,
            )
            for i in range(
                worker_count
            )
        ]
        parts = [f.result() for f in as_completed(futures)]
    elapsed = max(time.perf_counter() - started, 0.001)
    ok, err, lat = aggregate(parts)
    total = ok + err
    qps = ok / elapsed
    return {
        "name": "login",
        "endpoint": "/api/login",
        "requests": total,
        "success": ok,
        "errors": err,
        "error_rate": err / max(total, 1),
        "elapsed_seconds": elapsed,
        "qps": qps,
        "target_qps": required_target,
        "avg_ms": statistics.fmean(lat) if lat else 0,
        "p95_ms": percentile(lat, 95),
        "p99_ms": percentile(lat, 99),
        "target_met": ok > 0 and qps >= required_target and err == 0,
    }

def bench_agent(
    base,
    duration,
    workers,
    scale=1.0,
):
    target = (
        TARGETS["qps"]["agent"]
        * scale
    )

    # app.py currently serves with 32 Waitress
    # threads, so never create more than 32
    # simultaneous Agent workers.
    worker_count = max(
        1,
        min(
            workers,
            32,
        ),
    )

    started = (
        time.perf_counter()
    )

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as pool:
        futures = [
            pool.submit(
                agent_worker,
                base,
                duration,
                i,
                target,
                worker_count,
            )
            for i in range(
                worker_count
            )
        ]

        parts = [
            future.result()
            for future
            in as_completed(
                futures
            )
        ]

    elapsed = max(
        time.perf_counter()
        - started,
        0.001,
    )

    ok, err, lat = aggregate(
        parts
    )

    fallbacks = sum(
        part.get(
            "fallbacks",
            0,
        )
        for part in parts
    )

    total = ok + err

    qps = (
        ok / elapsed
    )

    return {
        "name":
            "agent",

        "endpoint":
            "/api/agent/chat",

        "requests":
            total,

        "success":
            ok,

        "errors":
            err,

        "fallbacks":
            fallbacks,

        "error_rate":
            err
            / max(
                total,
                1,
            ),

        "elapsed_seconds":
            elapsed,

        "qps":
            qps,

        "target_qps":
            target,

        "avg_ms":
            statistics.fmean(
                lat
            )
            if lat
            else 0,

        "p95_ms":
            percentile(
                lat,
                95,
            ),

        "p99_ms":
            percentile(
                lat,
                99,
            ),

        "target_met": (
            ok > 0
            and qps >= target
            and err == 0
            and fallbacks == 0
        ),
    }

def bench_writes(
    base,
    duration,
    workers,
    scale=1.0,
):
    required_start = (
        TARGETS["qps"][
            "start_charging"
        ]
        * scale
    )

    required_finish = (
        TARGETS["qps"][
            "end_charging"
        ]
        * scale
    )

    required_target = min(
        required_start,
        required_finish,
    )

    # Offer 10% above the requirement.
    # Pass/fail remains against the official
    # L1 target of 10 QPS.
    offered_target = (
        required_target
        * 1.10
    )

    worker_count = max(
        1,
        min(
            workers,
            100,
        ),
    )

    # ---------------------------------
    # Pre-authenticate OUTSIDE the
    # measured benchmark window.
    # ---------------------------------

    sessions = []
    csrf_tokens = []

    for i in range(worker_count):
        session = (
            requests.Session()
        )

        phone, password = USERS[
            i % len(USERS)
        ]

        try:
            csrf = login(
                session,
                base,
                phone,
                password,
            )

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ):
            raise RuntimeError(
                "Write benchmark "
                "pre-login failed for "
                f"{phone}"
            )

        sessions.append(
            session
        )

        csrf_tokens.append(
            csrf
        )

    start_event = (
        threading.Event()
    )

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as pool:

        futures = [
            pool.submit(
                write_cycle_worker,
                sessions[i],
                csrf_tokens[i],
                base,
                duration,
                i,
                offered_target,
                worker_count,
                start_event,
            )
            for i in range(
                worker_count
            )
        ]

        started = (
            time.perf_counter()
        )

        start_event.set()

        parts = [
            future.result()
            for future
            in as_completed(
                futures
            )
        ]

    elapsed = max(
        time.perf_counter()
        - started,
        0.001,
    )

    out = []

    for (
        key,
        name,
        endpoint,
        required_qps,
    ) in [
        (
            "start",
            "start_charging",
            "/api/orders",
            required_start,
        ),
        (
            "finish",
            "end_charging",
            "/api/orders/<id>/finish",
            required_finish,
        ),
    ]:

        ok = sum(
            p[key][0]
            for p in parts
        )

        err = sum(
            p[key][1]
            for p in parts
        )

        lat = [
            m
            for p in parts
            for m in p[key][2]
        ]

        total = ok + err

        qps = (
            ok / elapsed
        )

        out.append(
            {
                "name":
                    name,

                "endpoint":
                    endpoint,

                "requests":
                    total,

                "success":
                    ok,

                "errors":
                    err,

                "error_rate":
                    err
                    / max(
                        total,
                        1,
                    ),

                "elapsed_seconds":
                    elapsed,

                "qps":
                    qps,

                "target_qps":
                    required_qps,

                "offered_qps":
                    offered_target,

                "avg_ms":
                    statistics.fmean(
                        lat
                    )
                    if lat
                    else 0,

                "p95_ms":
                    percentile(
                        lat,
                        95,
                    ),

                "p99_ms":
                    percentile(
                        lat,
                        99,
                    ),

                "target_met": (
                    ok > 0
                    and qps
                        >= required_qps
                    and err == 0
                ),
            }
        )

    return out


def run(
    base,
    duration,
    workers,
    write_test,
    scale=1.0,
    agent_test=False,
):
    healthy, detail = (
        health_check(base)
    )

    if not healthy:
        raise RuntimeError(
            "Service health check "
            f"failed after retries: "
            f"{detail}"
        )

    results = [
        bench_login(
            base,
            duration,
            workers,
            scale,
        )
    ]

    results += bench_reads(
        base,
        duration,
        workers,
        scale,
    )

    if agent_test:
        results.append(
            bench_agent(
                base,
                duration,
                workers,
                scale,
            )
        )

    if write_test:
        results += bench_writes(
            base,
            duration,
            workers,
            scale,
        )

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:5000")
    ap.add_argument("--duration", type=float, default=30)
    ap.add_argument("--workers", type=int, default=60)
    ap.add_argument("--write-test", action="store_true")
    ap.add_argument(
        "--agent-test",
        action="store_true",
        help=(
            "Benchmark the real GLM-backed "
            "AI Agent. This consumes AI API "
            "credits."
        ),
    )
    ap.add_argument(
        "--stages",
        action="store_true",
        help="Run 25/50/75/100/125%% of the L1 target QPS after the main test",
    )
    ap.add_argument("--output", default="performance_report.json")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print(
        f"NCS {CAPACITY_LEVEL} capacity test -> {base}; "
        f"duration={args.duration}s workers={args.workers}; write_test={args.write_test}"
    )

    results = run(
        base,
        args.duration,
        args.workers,
        args.write_test,
        scale=1.0,
        agent_test=args.agent_test,
    )
    stress = []
    if args.stages:
        for ratio in (0.25, 0.50, 0.75, 1.00, 1.25):
            stage_workers = max(1, min(120, args.workers))
            stage_duration = max(5, args.duration / 2)
            print(
                f"\nStress stage {ratio:.0%} target load: "
                f"{stage_workers} workers x {stage_duration:.1f}s"
            )
            try:
                sr = run(
                    base,
                    stage_duration,
                    stage_workers,
                    args.write_test,
                    scale=ratio,

                    # Don't repeatedly spend GLM API credits
                    # during all five stress stages.
                    agent_test=False,
                )
            except RuntimeError as exc:
                sr = [{"name": "health", "target_met": False, "error": str(exc)}]
                print(f"  Stage skipped: {exc}")
            stress.append({
                "target_ratio": ratio,
                "workers": stage_workers,
                "duration": stage_duration,
                "results": sr,
            })
            # Let SQLite/WAL and the web server recover before increasing load.
            time.sleep(2)

    payload = {
        "capacity_level": CAPACITY_LEVEL,
        "capacity": TARGETS,
        "base_url": base,
        "duration": args.duration,
        "workers": args.workers,
        "write_test": args.write_test,
        "agent_test": args.agent_test,
        "stages": stress,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
        "methodology": {
            "load_model": "target-QPS paced open-loop load",
            "stage_ratios": [0.25, 0.50, 0.75, 1.00, 1.25] if args.stages else [],
            "pass_rule": "successful QPS >= offered target and error rate == 0",
            "writes": "real /api/orders start + finish endpoints when --write-test is enabled",
            "agent": (
                "real /api/agent/chat with "
                "agent_mode=glm required for success"
                if args.agent_test
                else "not tested"
            ),
        },
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# NCS L1 容量与性能测试报告",
        "",
        f'- 容量等级：{CAPACITY_LEVEL}（{TARGETS["name"]}）',
        f"- 服务地址：{base}",
        f"- 主测试持续时间：{args.duration} 秒",
        f"- 最大工作线程：{args.workers}",
        f'- 写场景：{"启用（使用 L1 测试夹具）" if args.write_test else "关闭（只读安全模式）"}',
        (
            "- AI Agent 场景："
            + (
                "启用（真实 GLM API）"
                if args.agent_test
                else "关闭"
            )
        ),
        "- 负载模型：按目标 QPS 进行开环限速，而不是把 worker 数直接当作 QPS。",
        "",
        "| 场景 | 实测 QPS | 目标 QPS | Avg ms | P95 ms | P99 ms | 错误率 | 达标 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        met = "是" if r["target_met"] else "否"
        lines.append(
            f'| {r["name"]} | {r["qps"]:.2f} | {r["target_qps"]:.2f} | '
            f'{r["avg_ms"]:.2f} | {r["p95_ms"]:.2f} | {r["p99_ms"]:.2f} | '
            f'{r["error_rate"]:.2%} | {met} |'
        )

    lines += [
        "",
        "## 验收判定",
        "- 单项达标条件：实测成功 QPS ≥ 对应目标 QPS 且错误率 = 0。",
        "- 压力阶段按 25% / 50% / 75% / 100% / 125% 的目标 QPS 逐级增加。",
        "- 写场景使用真实 `/api/orders` 业务接口，覆盖订单创建、结算和电桩释放。",
        "- Agent 场景只有返回 `agent_mode=glm` 才计为成功；本地 fallback 不计入达标请求。",
    ]
    if stress:
        lines += [
            "",
            "## 压力分级结果",
            "",
            "| 目标负载 | 达标场景数 | 总场景数 |",
            "|---:|---:|---:|",
        ]
        for st in stress:
            rr = st["results"]
            met = sum(1 for r in rr if r.get("target_met"))
            lines.append(f'| {st["target_ratio"]:.0%} | {met} | {len(rr)} |')

    Path("PERFORMANCE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    for r in results:
        print(
            f'{r["name"]}: qps={r["qps"]:.2f} target={r["target_qps"]:.2f} '
            f'p95={r["p95_ms"]:.2f}ms err={r["error_rate"]:.2%} '
            f'-> {"PASS" if r["target_met"] else "FAIL"}'
        )
    print("Written:", args.output, "and PERFORMANCE_REPORT.md")


if __name__ == "__main__":
    main()
