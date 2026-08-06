# Profile README setup

This repository powers **https://github.com/canekin**.

## What updates itself

| Piece | How | Cadence |
| --- | --- | --- |
| Stats / languages / contributions SVGs | `.github/workflows/stats.yml` → `scripts/generate_stats.py` | **hourly** (`:41` UTC) + manual |
| Recently pushed projects (top 5) | same workflow → `scripts/generate_projects.py` | hourly + manual |
| Skills / connect / about SVGs | same workflow | hourly + manual |
| Contribution snake | same workflow → Platane/snk + `scripts/frame_snake.py` | **hourly** (was daily) |
| Manual snake-only | `.github/workflows/snake.yml` | manual only |

One workflow refreshes everything in a single commit (avoids push races between stats and snake).

GitHub `schedule` is **best-effort**: under load, runs can be delayed or dropped (especially near `:00`). The cron uses minute `41` to reduce that. If a run fails with “job was not acquired by Runner” / internal server error, that is a GitHub infra blip — re-run from Actions → **Refresh profile assets** → **Run workflow**.

### Rate limits (hourly is fine)

Authenticated PAT budget is roughly **5,000 REST requests/hour** and **5,000 GraphQL points/hour**.

One full refresh uses on the order of **~20–40 API calls** (repo list, languages per repo, a couple GraphQL contribution queries, Platane/snk). That is well under 1% of the hourly budget, even with snake every hour.

## Secrets

Default `GITHUB_TOKEN` **cannot** list your private repositories or private contribution days.

1. Fine-grained PAT (recommended): resource owner = you, **All repositories**, **Contents: Read**, **Metadata: Read**, optional Account **Events: Read**
2. Repo → **Settings → Secrets and variables → Actions**
3. Secret name: `PROFILE_TOKEN`
4. Actions → **Refresh profile assets** → **Run workflow**

Keep **Settings → Profile → Contributions & activity → Include private contributions on my profile** enabled if you want private days on the public graph / snake.

## Editing content

| What | Where |
| --- | --- |
| Project descriptions / stacks | `CURATED` in `scripts/generate_projects.py` |
| Skills layers | `LAYERS` in `scripts/generate_skills.py` (+ `scripts/skill_icons.json`) |
| Connect links / email | `CHANNELS` in `scripts/generate_connect.py` |
| About fields | `FIELDS` in `scripts/generate_about.py` |

After changing a generator script, either push (workflow auto-runs on those paths) or run **Refresh profile assets** manually. Do not hand-edit `generated/*.svg` for values that scripts overwrite.

## Local run

```bash
python scripts/generate_stats.py
python scripts/generate_projects.py
python scripts/generate_skills.py
python scripts/generate_connect.py
python scripts/generate_about.py
```

```powershell
$env:PROFILE_TOKEN = "github_pat_..."
python scripts/generate_stats.py
python scripts/generate_projects.py
```
