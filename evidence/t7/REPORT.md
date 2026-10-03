# T7 concurrency goodput

With fixed storage resources and payload, four concurrent requests improve application transfer goodput relative to one.

Profile: 32 x 4 MiB = 128 MiB per phase

## Metric definitions
- Goodput = successful bytes / 2^20 / phase wall seconds; PUT and GET are reported separately.
- GET phase wall time includes SHA-256 verification and bookkeeping; per-request latency ends after the response body is read and excludes hashing.
- p95 is nearest-rank among successful requests within each phase/trial; n=32 is a coarse tail estimate. Failed requests are counted separately.
- Success is successful requests / 32. A GET counts as verified only when its SHA-256 matches the expected hash; target is 192 PUTs and 192 verified GETs.
- The comparison uses the median phase goodput across three trials per concurrency; trial p95 values remain separate and are not pooled.

| trial | c | PUT MiB/s | PUT p95 ms | PUT ok | PUT fail | GET MiB/s | GET p95 ms | GET ok | GET fail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| r1-c1 | 1 | 107.8313 | 46.6 | 32/32 | 0 | 377.1586 | 28.8 | 32/32 | 0 |
| r1-c4 | 4 | 102.7116 | 279.5 | 32/32 | 0 | 250.4873 | 99.4 | 32/32 | 0 |
| r2-c4 | 4 | 101.5000 | 226.0 | 32/32 | 0 | 211.1987 | 100.1 | 32/32 | 0 |
| r2-c1 | 1 | 74.9773 | 94.9 | 32/32 | 0 | 232.8915 | 33.4 | 32/32 | 0 |
| r3-c1 | 1 | 90.3279 | 67.8 | 32/32 | 0 | 233.7964 | 33.0 | 32/32 | 0 |
| r3-c4 | 4 | 95.8013 | 258.3 | 32/32 | 0 | 218.4606 | 91.4 | 32/32 | 0 |

## Comparison (median of three trials per concurrency)

- PUT: median(c=1)=90.3279 MiB/s, median(c=4)=101.5000 MiB/s, ratio=1.1237 -> supports: c=4 median goodput is higher
- GET: median(c=1)=233.7964 MiB/s, median(c=4)=218.4606 MiB/s, ratio=0.9344 -> does not support: c=4 median goodput is lower

## Interpretation

The c=4 median PUT goodput was 12.4% higher, while median GET goodput was 6.6% lower. The result is phase-dependent and inconclusive for a blanket claim that four concurrent requests improve goodput; the observed difference does not identify a cause.

Integrity: 192/192 valid PUTs, 192/192 verified GETs.

## Confounders
- Cache: PUTs may warm kernel/PVC/object-store cache before GET.
- CPU: ingestor limit 500m; objects store limit 1 CPU — four threads can queue on CPU.
- Network: ClusterIP on Docker Desktop, not a dedicated storage fabric.
- Backend: one seaweedfs `mini` replica, 4Gi PVC; concurrency is not scale-out.
- Shared cluster: other class pods and node processes compete for CPU, disk, and net.

- Sampling limitation: `kubectl top` returned Metrics API errors; see `samples.txt`. Pod status was sampled.
Negative or inconclusive ratios are acceptable; no absolute MiB/s threshold is required.
