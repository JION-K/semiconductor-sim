#!/usr/bin/env python3
"""
Parity harness for Stage 2.

Compares Python backend vs Spring facade response drift for selected endpoints.
Usage:
  python3 scripts/parity_harness.py --py http://127.0.0.1:8000 --spring http://127.0.0.1:8080 --steps 30
"""

import argparse
import json
import urllib.request


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def post(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def summarize_status(s):
    return {
        "time": s.get("time"),
        "is_paused": s.get("is_paused"),
        "is_done": s.get("is_done"),
        "active": len(s.get("active_lots", [])),
        "processing": (s.get("kpi") or {}).get("processing_lots"),
        "finished": (s.get("kpi") or {}).get("finished_lots"),
        "progress_signature": s.get("progress_signature"),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--py", default="http://127.0.0.1:8000")
    p.add_argument("--spring", default="http://127.0.0.1:8080")
    p.add_argument("--steps", type=int, default=20)
    args = p.parse_args()

    # normalize both sides
    post(f"{args.py}/api/control/reset")
    post(f"{args.spring}/api/control/reset")
    post(f"{args.py}/api/control/resume")
    post(f"{args.spring}/api/control/resume")

    mismatches = []
    for i in range(args.steps):
        py_s = post(f"{args.py}/api/step")
        sp_s = post(f"{args.spring}/api/step")
        a = summarize_status(py_s)
        b = summarize_status(sp_s)
        if a != b:
            mismatches.append({"step": i + 1, "python": a, "spring": b})

    report = {
        "steps": args.steps,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:10],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
