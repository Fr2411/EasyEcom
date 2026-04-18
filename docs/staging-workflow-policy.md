# Staging Workflow Policy (TEA-196 / TEA-190A)

## Branch Model
- `feature/*`: implementation branches, no production deploy.
- `develop`: staging integration branch.
- `main`: production release branch.

## Required Flow
1. Run local internal preview before push:
   - `./scripts/local_preview_before_push.sh`
2. Open PRs into `develop` first.
3. Merge into `main` only after staging validation is complete.
4. Production backend deploy is manual-only from GitHub Actions `Deploy Backend` (`workflow_dispatch`).

## Required Checks
- GitHub status check: `Staging Policy Gate / verify`
- This check runs from `.github/workflows/staging-policy-gate.yml` and uses `./scripts/staging_quality_gate.sh`.

## Branch Protection Rollout
Apply branch protection for `main` and `develop` with:

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
- Frontend deploy/staging URL setup is handled in TEA-197.
