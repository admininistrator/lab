# Task 5 evidence index
Context: docker-desktop, namespace bd-g06. One storage replica on PVC object-data.

## Setup
- evidence/t5/seed.jsonl: owner seeded 2 buckets x 2 fixtures (4 lines, all http 200).
- evidence/t5/r1-c1.jsonl: benchmark r1-c1, concurrency 1, 32 objects x 4 MiB; creates the data used for recovery.

## First attempt (valid for integrity and UIDs, NOT valid for timing)
The canary ended at 15:52:39Z, before the Pod was deleted at 15:53:04Z, so it saw no failure.
- evidence/t5/before-recovery.jsonl, after-recovery.jsonl: verify of 32 objects before and after.
- evidence/t5/pod-before.yaml, pod-after.yaml, pvc-before.yaml, pvc-after.yaml: Pod and PVC state.
- evidence/t5/canary.jsonl, delete-time.txt: canary log and delete time.

## Second attempt, run2 (valid run, used in the summary)
Canary started 15:57:31Z, Pod deleted 15:58:01Z, canary ended 16:00:31Z.
- evidence/t5/run2/before-recovery.jsonl, after-recovery.jsonl: 32 objects verified, hashes identical.
- evidence/t5/run2/pod-before.yaml, pod-after.yaml, pvc-before.yaml, pvc-after.yaml: Pod UID changed, PVC UID unchanged.
- evidence/t5/run2/canary.jsonl, delete-time.txt: 7 failed reads, observed interruption about 7.03 s.
- evidence/t5/run2/S06.json, S08.json, S10.json: access retests after recovery (200, 403 AccessDenied, 403 AccessDenied).
- evidence/t5/run2/events.txt, storage-log.txt: namespace events and log of the Pod running at export time; scanned for credentials, none found.

## Summary and cross-check
- recovery-summary.json: measured values for run2.
- evidence/task5-check-task2.txt: independent check of the Task 2 storage evidence.

## Not proven
HA, backup, node-loss durability. One trial only; client-side timing at about 1 s resolution.