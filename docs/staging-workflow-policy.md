# Main Branch Workflow Policy

## Branch Model
- `main`: primary implementation and production release branch.

## Required Flow
1. Implement changes directly on local `main`.
2. Run validation before push:
   - `./scripts/staging_quality_gate.sh`
3. Commit and push directly to `origin/main`.
4. Frontend production deploy auto-triggers from `main` push.
5. Production backend deploy remains manual-only from GitHub Actions `Deploy Backend` (`workflow_dispatch`).

## Required Checks
- GitHub status check: `Staging Policy Gate / verify`
- This check runs from `.github/workflows/staging-policy-gate.yml` and uses `./scripts/staging_quality_gate.sh`.

## Branch Protection Rollout
Apply branch protection for `main` with:

```bash
./scripts/apply_branch_protection.sh
```

The rollout script enforces:
- required status check (`Staging Policy Gate / verify`),
- strict up-to-date branch checks,
- PR review requirement,
- no force push or branch deletion,
- linear history.

## Notes
- This policy keeps CI/check definitions single-sourced in `scripts/staging_quality_gate.sh` (local and CI both use the same script).
- `main` push keeps current production behavior: frontend deploy is automatic, backend deploy is manual.
