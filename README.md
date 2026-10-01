# Big Data Lab - Group 6

This repository contains the team's Kubernetes manifests, scripts, and machine-readable evidence for the lab.

## Current status

**Task 1 — Tenant Guardrails: COMPLETE**

The completed Task 1 demonstrates:

- Kubernetes namespace: `bd-g06`
- `ResourceQuota/team-budget`
- `NetworkPolicy/private-object-store`
- read-only `observer` ServiceAccount, Role, and RoleBinding
- positive admission test: small Pod admitted successfully
- negative admission test: 3-CPU Pod rejected with `Forbidden: exceeded quota`
- reproducible manifests and evidence saved under `manifests/` and `evidence/`

---

## Important: GitHub does not contain the Kubernetes cluster state

Cloning this repository gives you the manifests, scripts, and evidence, but it does **not** copy the first student's local Docker Desktop Kubernetes cluster.

Each pc has its own local Kubernetes cluster.

Therefore, before starting Task 2 on another pc, you must recreate the Task 1 **prerequisite resources** in that pc's Docker Desktop Kubernetes cluster.

You do **not** need to manually repeat all Task 1 experiments.

Use the bootstrap script described below.

---

