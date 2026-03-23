# Repo Maintenance Summary

**Locator Update**
- Changed Compass Mobile button locator to a contains match to accommodate label changes like "Compass Mobile (Leaving Soon...)".
- Reference: [pages/login_page.py](pages/login_page.py#L196).

**Ignored/Untracked Artifacts**
- Python caches and bytecode: [__pycache__/](__pycache__/), `*.pyc`.
- Logs and artifacts: [log/](log/), [artifacts/](artifacts/), `*.log`.
- WebDriver binaries: [msedgedriver.exe](msedgedriver.exe).
- Generated outputs: [GlassResults.txt](GlassResults.txt) — kept ignored.

**Local-Only Data Files**
- CSVs in [data/](data/): [GlassDamageWorkItemScript.csv](data/GlassDamageWorkItemScript.csv), [GlassDataParser.csv](data/GlassDataParser.csv), [GlassWorkItems.csv](data/GlassWorkItems.csv).
- Marked with `git update-index --skip-worktree` locally to suppress status noise while retaining version control.

**Commands**
- Mark CSVs as local-only:
  - git update-index --skip-worktree data/GlassDamageWorkItemScript.csv
  - git update-index --skip-worktree data/GlassDataParser.csv
  - git update-index --skip-worktree data/GlassWorkItems.csv
- Undo local-only flags:
  - git update-index --no-skip-worktree data/GlassDamageWorkItemScript.csv
  - git update-index --no-skip-worktree data/GlassDataParser.csv
  - git update-index --no-skip-worktree data/GlassWorkItems.csv

**Notes**
- skip-worktree is a local flag; teammates’ clones are unaffected.
- If upstream changes a CSV, temporarily remove skip-worktree to pull/merge cleanly.
