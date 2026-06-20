# Watch Tracker on GitHub Actions — Setup Guide

Run the Longines moonphase monitor hourly in the cloud (no PC needed) using a
free GitHub Actions scheduled workflow. New listings push to your phone via ntfy.

---

## A. Files to copy into your cloned repo

From the `Watch-Tracker` folder, copy these into the **root** of your local repo
clone (keep the `.github/workflows/` path exactly):

```
your-repo/
├─ watch_monitor.py
├─ requirements.txt
└─ .github/
   └─ workflows/
      └─ monitor.yml
```

Optional (nice to have, not required by the Action):
- `data/monitor_state.json` — copy your **local** one if you want to carry over dedup
  history so the cloud run doesn't re-alert on listings you've already seen. If you
  don't copy it, the first cloud run just seeds a fresh baseline silently.
- `README.md`, `HANDOFF_SUMMARY.md`, `requested_watches.md` — for context.

You do **not** need `setup.command`, `setup.bat`, or `seen_listings.json` for the
GitHub Actions version (they're for local running).

---

## B. One decision first: is your repo public or private?

- **Private repo (recommended):** Free Actions minutes are 2,000/month; an hourly
  ~1-minute job uses ~720/month — comfortably free. Your ntfy topic won't be world-
  readable.
- **Public repo:** Actions minutes are unlimited, BUT anyone can read your files. Do
  **not** hardcode your ntfy topic in `watch_monitor.py` (anyone could read your
  alerts or spam you). Use the secret in step C and change the topic line in
  `watch_monitor.py` back to a placeholder:
  ```python
  NTFY_TOPIC = os.getenv("NTFY_TOPIC") or "REPLACE-ME-watchtracker-xxxx"
  ```
  The secret will supply the real topic at runtime.

(ntfy topics are "security by obscurity" — a long random topic name is the only
thing keeping others out, so don't publish it.)

---

## C. GitHub configuration (do these in the repo's web UI)

### 1. Add your ntfy topic as a secret
- Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
- Name: `NTFY_TOPIC`
- Value: `watchtracker-noelrodriguez-12251996`
- Save.

### 2. Give the workflow permission to push state back
The job commits `data/monitor_state.json` back to the repo each run. That needs write access.
- Repo → **Settings** → **Actions** → **General** → scroll to **Workflow permissions**
- Select **Read and write permissions** → **Save**.
- (If this is left on read-only, the run still scans and pushes alerts fine, but the
  "Persist dedup state" step will fail and you'll get repeat alerts.)

### 3. Make sure Actions are enabled
- Repo → **Settings** → **Actions** → **General** → **Allow all actions and reusable workflows** (or at least allow GitHub-owned actions). Save.

---

## D. Push the files and test

1. Commit and push the copied files to GitHub:
   ```bash
   git add watch_monitor.py requirements.txt .github/workflows/monitor.yml
   git commit -m "Add Watch Tracker hourly monitor"
   git push
   ```
2. Go to the repo's **Actions** tab. You should see **Watch Tracker Monitor**.
3. **Test the push now** (don't wait an hour):
   - Click **Watch Tracker Monitor** → **Run workflow** →
     set **test_push** to `true` → **Run workflow**.
   - In ~30–60s your phone should get the test ntfy push. ✅
   - (Make sure the ntfy app is subscribed to your exact topic first.)
4. **Seed the baseline:** click **Run workflow** again with **test_push = false**.
   The first real run records current listings silently (no alerts). Check the run
   log — you'll see `First run: baseline saved`.
5. After that, the hourly schedule takes over automatically. You'll get a push only
   when a genuinely **new** listing appears.

---

## E. Using Claude Code in the repo (optional)

Once cloned, you can open Claude Code in the repo directory and ask it to help tweak
search terms, add sources, or debug a failed run. Everything it needs is in the repo:
`watch_monitor.py` (the logic) and `.github/workflows/monitor.yml` (the schedule).
Point it at a failed Actions run log and it can diagnose from there.

---

## F. Honest caveats (worth knowing)

| Topic | What to expect |
|---|---|
| **Timing** | GitHub cron is **UTC** and scheduled runs are often **delayed 10–30 min** under load. Fine for hourly deal checks; not for to-the-second precision. |
| **Datacenter IP blocking** | eBay and especially **Chrono24 may block GitHub's IPs** more than your home network would. Reddit's JSON keeps working. So cloud coverage can be slightly weaker than running on your Mac — check a few run logs to see what each source returns. |
| **60-day inactivity** | GitHub disables scheduled workflows if a repo has no activity for 60 days. The state-commit each run keeps it active, so this won't bite you. |
| **Free minutes** | Private repo = 2,000 min/month free; this job uses ~720. No card needed. |
| **Secrets** | Logs never print the topic; it's passed as an env var from the secret. |

---

## G. Quick troubleshooting

- **No test push received:** confirm the ntfy app is subscribed to the exact topic,
  and that the `NTFY_TOPIC` secret matches it character-for-character.
- **"Persist dedup state" step fails / repeated alerts:** you missed step C2 (set
  workflow permissions to Read and write).
- **Workflow not appearing in Actions tab:** the file must be at
  `.github/workflows/monitor.yml` exactly, and Actions must be enabled (step C3).
- **Few/no eBay or Chrono24 results in logs:** likely datacenter-IP blocking (see F).
  Reddit should still return results; tell Claude Code and it can add resilience.
