# Profile README setup

This repository powers **https://github.com/canekin**.

## What updates itself

| Piece | How | Cadence |
| --- | --- | --- |
| Public / private repo counts + custom SVG | `.github/workflows/stats.yml` → `scripts/generate_stats.py` | every 6 hours (+ manual) |
| Contribution snake | `.github/workflows/snake.yml` (Platane/snk) | daily |
| Activity graph / language cards | third-party SVG APIs embedded in README | on each profile view (cached) |

You do **not** need to edit the README for stats — Actions commits refreshed numbers into `generated/stats.svg` and the marked table.

## Enable private repo counts (recommended)

Default `GITHUB_TOKEN` inside Actions **cannot** list your private repositories.

1. Create a Personal Access Token:
   - Classic: enable `repo` (and `read:user` if available)
   - Fine-grained: resource owner = you, repository access = **All repositories**, permissions → **Contents: Read**, **Metadata: Read**
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `PROFILE_TOKEN`  
   Value: the token
4. Actions → **Update profile stats** → **Run workflow**

After that, the SVG and table show real `x public · y private`.

## Manual trigger

GitHub → Actions → pick workflow → **Run workflow**.

Locally (optional):

```bash
python scripts/generate_stats.py
```

With private visibility:

```bash
# PowerShell
$env:PROFILE_TOKEN = "ghp_..."
python scripts/generate_stats.py
```
