"""Compute T7 metrics from bench JSONL. Does not pool p95 across trials."""

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

MIB = 1024 * 1024
TRIALS = [
    ("r1-c1", 1),
    ("r1-c4", 4),
    ("r2-c4", 4),
    ("r2-c1", 1),
    ("r3-c1", 1),
    ("r3-c4", 4),
]


def load_rows(path):
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def nearest_rank_p95(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def phase_from_rows(rows, phase):
    reqs = [
        r
        for r in rows
        if r.get("kind") != "summary" and r.get("op") == phase
    ]
    summaries = [
        r
        for r in rows
        if r.get("kind") == "summary" and r.get("phase") == phase
    ]
    return reqs, summaries[0] if summaries else None


def check_summary(reqs, summary, phase, n_expected):
    good = [r for r in reqs if r.get("ok")]
    failed = [r for r in reqs if not r.get("ok")]
    n = len(reqs)
    wall = summary["wall_s"]
    bytes_ok = sum(r.get("bytes", 0) for r in good)
    goodput = bytes_ok / MIB / wall if wall else None
    p95 = nearest_rank_p95([r["ms"] for r in good if "ms" in r])

    mismatches = []
    if n != n_expected:
        mismatches.append(f"n={n} expected {n_expected}")
    if summary.get("successes") != len(good):
        mismatches.append("summary successes != request ok count")
    if not math.isclose(summary["goodput_MiB_s"], goodput, rel_tol=1e-9, abs_tol=1e-9):
        mismatches.append("goodput mismatch vs recomputation")
    helper_p95 = summary.get("p95_success_ms")
    if helper_p95 is None or p95 is None:
        if helper_p95 is not p95:
            mismatches.append("p95 mismatch vs recomputation")
    elif not math.isclose(helper_p95, p95, rel_tol=1e-9, abs_tol=1e-6):
        mismatches.append("p95 mismatch vs recomputation")
    if phase == "get":
        hash_fail = [
            r for r in reqs if r.get("ok") is False and r.get("hash_ok") is False
        ]
        if hash_fail:
            mismatches.append(f"{len(hash_fail)} GET hash mismatches")

    return {
        "n": n,
        "successes": len(good),
        "failed": len(failed),
        "success_ratio": len(good) / n_expected,
        "wall_s": wall,
        "goodput_MiB_s": goodput,
        "p95_success_ms": p95,
        "failed_errors": [r.get("error") for r in failed],
        "mismatches": mismatches,
        "helper_summary": {
            "goodput_MiB_s": summary["goodput_MiB_s"],
            "p95_success_ms": summary.get("p95_success_ms"),
            "successes": summary.get("successes"),
        },
    }


def median(values):
    return statistics.median(values)


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence/t7")
    n_expected = None
    report = {
        "profile": None,
        "hypothesis": (
            "With fixed storage resources and payload, four concurrent "
            "requests improve application transfer goodput relative to one."
        ),
        "trials": [],
    }

    put_by_c = defaultdict(list)
    get_by_c = defaultdict(list)
    put_ok = get_ok = 0

    for name, conc in TRIALS:
        path = root / f"{name}.jsonl"
        if not path.exists():
            report["trials"].append({"run": name, "missing": True})
            continue
        rows = load_rows(path)
        put_reqs, put_sum = phase_from_rows(rows, "put")
        get_reqs, get_sum = phase_from_rows(rows, "get")
        if put_sum:
            n_expected = put_sum.get("n")
        trial = {
            "run": name,
            "concurrency": conc,
            "put": check_summary(put_reqs, put_sum, "put", n_expected or 32) if put_sum else None,
            "get": check_summary(get_reqs, get_sum, "get", n_expected or 32) if get_sum else None,
        }
        report["trials"].append(trial)
        if trial["put"]:
            put_ok += trial["put"]["successes"]
            put_by_c[conc].append(trial["put"]["goodput_MiB_s"])
        if trial["get"]:
            get_ok += trial["get"]["successes"]
            get_by_c[conc].append(trial["get"]["goodput_MiB_s"])

    def compare(phase, by_c):
        m1 = median(by_c[1]) if len(by_c[1]) == 3 else None
        m4 = median(by_c[4]) if len(by_c[4]) == 3 else None
        ratio = (m4 / m1) if m1 not in (None, 0) and m4 is not None else None
        if ratio is None:
            verdict = "incomplete"
        elif ratio > 1:
            verdict = "supports: c=4 median goodput is higher"
        elif ratio < 1:
            verdict = "does not support: c=4 median goodput is lower"
        else:
            verdict = "inconclusive: medians equal"
        return {
            "phase": phase,
            "goodput_c1": by_c[1],
            "goodput_c4": by_c[4],
            "median_c1": m1,
            "median_c4": m4,
            "ratio_c4_over_c1": ratio,
            "verdict": verdict,
        }

    objects = n_expected or 32
    report["profile"] = f"{objects} x 4 MiB = {objects * 4} MiB per phase"
    target = 6 * objects
    report["integrity"] = {
        "valid_puts": put_ok,
        "verified_gets": get_ok,
        "target_puts": target,
        "target_gets": target,
    }
    report["comparison"] = [
        compare("put", put_by_c),
        compare("get", get_by_c),
    ]
    put_ratio = report["comparison"][0]["ratio_c4_over_c1"]
    get_ratio = report["comparison"][1]["ratio_c4_over_c1"]
    if put_ratio is not None and get_ratio is not None:
        put_direction = "higher" if put_ratio >= 1 else "lower"
        get_direction = "higher" if get_ratio >= 1 else "lower"
        report["interpretation"] = (
            f"The c=4 median PUT goodput was {abs(put_ratio - 1) * 100:.1f}% {put_direction}, "
            f"while median GET goodput was {abs(get_ratio - 1) * 100:.1f}% {get_direction}. "
            "The result is phase-dependent and inconclusive for a blanket claim that "
            "four concurrent requests improve goodput; the observed difference does "
            "not identify a cause."
        )
    else:
        report["interpretation"] = (
            "The comparison is incomplete because all three trials at each concurrency "
            "were not available."
        )
    report["notes"] = [
        "Goodput = successful bytes / 2^20 / phase wall seconds.",
        "GET wall time includes SHA-256 verify and bookkeeping; per-request ms does not include hashing.",
        "p95 is nearest-rank among successful requests in that phase/trial; n=32 is a coarse tail.",
        "Average of trial p95s is not a pooled p95 and is not reported as one.",
        "Only thread concurrency changed; this is not storage scale-out.",
        "Confounders: page/object cache after PUT, client CPU limit 500m, store CPU limit 1, "
        "in-cluster Docker Desktop network, single seaweedfs mini replica, shared-cluster class load.",
    ]
    samples_path = root / "samples.txt"
    if samples_path.exists() and "Metrics API not available" in samples_path.read_text(
        encoding="utf-8", errors="replace"
    ):
        report["notes"].append(
            "kubectl top was sampled, but the cluster Metrics API was unavailable; "
            "the errors are preserved in samples.txt. Pod status was sampled."
        )

    out_json = root / "analysis.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# T7 concurrency goodput",
        "",
        report["hypothesis"],
        "",
        f"Profile: {report['profile']}",
        "",
        "## Metric definitions",
        "- Goodput = successful bytes / 2^20 / phase wall seconds; PUT and GET are reported separately.",
        "- GET phase wall time includes SHA-256 verification and bookkeeping; per-request latency ends after the response body is read and excludes hashing.",
        "- p95 is nearest-rank among successful requests within each phase/trial; n=32 is a coarse tail estimate. Failed requests are counted separately.",
        "- Success is successful requests / 32. A GET counts as verified only when its SHA-256 matches the expected hash; target is 192 PUTs and 192 verified GETs.",
        "- The comparison uses the median phase goodput across three trials per concurrency; trial p95 values remain separate and are not pooled.",
        "",
        "| trial | c | PUT MiB/s | PUT p95 ms | PUT ok | PUT fail | GET MiB/s | GET p95 ms | GET ok | GET fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t in report["trials"]:
        if t.get("missing") or not t.get("put") or not t.get("get"):
            lines.append(f"| {t['run']} |  | missing |  |  |  |  |  |")
            continue
        p, g = t["put"], t["get"]
        n = p["n"]
        lines.append(
                "| {run} | {c} | {pput:.4f} | {pp95:.1f} | {pok}/{n} | {pfail} | {gput:.4f} | {gp95:.1f} | {gok}/{n} | {gfail} |".format(
                run=t["run"],
                c=t["concurrency"],
                pput=p["goodput_MiB_s"],
                pp95=p["p95_success_ms"],
                pok=p["successes"],
                    pfail=p["failed"],
                n=n,
                gput=g["goodput_MiB_s"],
                gp95=g["p95_success_ms"],
                gok=g["successes"],
                    gfail=g["failed"],
            )
        )

    lines += ["", "## Comparison (median of three trials per concurrency)", ""]
    for cmp_ in report["comparison"]:
        lines.append(
            "- {phase}: median(c=1)={m1:.4f} MiB/s, median(c=4)={m4:.4f} MiB/s, "
            "ratio={ratio:.4f} -> {verdict}".format(
                phase=cmp_["phase"].upper(),
                m1=cmp_["median_c1"] or float("nan"),
                m4=cmp_["median_c4"] or float("nan"),
                ratio=cmp_["ratio_c4_over_c1"] or float("nan"),
                verdict=cmp_["verdict"],
            )
        )

    lines += ["", "## Interpretation", "", report["interpretation"]]

    integ = report["integrity"]
    lines += [
        "",
        f"Integrity: {integ['valid_puts']}/{integ['target_puts']} valid PUTs, "
        f"{integ['verified_gets']}/{integ['target_gets']} verified GETs.",
        "",
        "## Confounders",
        "- Cache: PUTs may warm kernel/PVC/object-store cache before GET.",
        "- CPU: ingestor limit 500m; objects store limit 1 CPU — four threads can queue on CPU.",
        "- Network: ClusterIP on Docker Desktop, not a dedicated storage fabric.",
        "- Backend: one seaweedfs `mini` replica, 4Gi PVC; concurrency is not scale-out.",
        "- Shared cluster: other class pods and node processes compete for CPU, disk, and net.",
        "",
        "Negative or inconclusive ratios are acceptable; no absolute MiB/s threshold is required.",
    ]
    if any("Metrics API was unavailable" in note for note in report["notes"]):
        lines.insert(
            lines.index("Negative or inconclusive ratios are acceptable; no absolute MiB/s threshold is required."),
            "- Sampling limitation: `kubectl top` returned Metrics API errors; see `samples.txt`. Pod status was sampled.",
        )
    (root / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
