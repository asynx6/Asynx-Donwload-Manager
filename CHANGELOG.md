# Changelog

All notable changes to AsynxDL are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-07-03

### Stability
- **Filename resolution** — New `resolve_filename()` helper deterministically resolves
  the displayed/saved name. URL-encoded characters (`%20`, `%2D`, etc.) now rendered
  correctly from second 0 — no more "A" placeholder when server `Content-Disposition`
  is missing on URLs like `https://archive.org/download/.../Grand%20Theft%20Auto%20-%20San%20Andreas%20PC.rar`.
- **Parts cleanup** — New `backend/core/parts_dir.py` module centralises
  `purge_all_parts_for(task_id)` and `purge_all_orphans()`. Pause/cancel/delete
  paths now consistently purge legacy `{id}.part*` files, hidden `.{id}.part*`
  files, and stale `.{id}.final` artifacts.
- **Cancel preserves history** — `DownloadTask.cancel()` no longer deletes the
  metadata `.json`. Record persists in `data/queue/completed/` with status
  `CANCELLED` so the user can retry without re-fetching `Content-Length`.
- **Race-safe pause/resume** — `DownloadManager` pause/resume/delete locks guard
  the active-task table; metadata-only tasks in the `completed/` folder now
  return a stable view JSON instead of a 404.
- **Throttled parts polling** — `_update_downloaded_size_from_parts()` is gated
  to ≤1 refresh per second. With 8 worker threads on a 4 GB RAM laptop, the
  previous per-tick `os.path.getsize` hammered the event loop.
- **Chunk buffer 32 KB** — Default `_CHUNK_BUFFER` reduced from 64 KB to 32 KB
  to suit slow-network consumers and machines with limited memory.

### Networking / startup
- **Exponential backoff** — `_wait_for_backend()` retries the `/status` probe
  with delays `0.2 → 0.4 → 0.8 → 1.5 → 2.0s`, capped at 10 s.
- **Single-instance safe** — When port `58296` is already in use, AsynxDL
  exits with `[INFO] AsynxDL already running.` instead of fighting uvicorn
  for the bind.
- **Splash root-share** — Splash window withdraws instead of destroying so
  the main CTk root is reused. Eliminates the second-window duplicate at
  cold start observed in v1.0.0.
- **Daemon uvicorn thread** — `start_server_thread()` was already
  `daemon=True`, ensuring the process exits cleanly with Ctrl-C.

### UX
- **Tray icon swap** — Tray icon changes between `idle` (brand blue) and
  `active` (green) based on `_count_active_downloads()` in the App.
- **Tray toast on close** — When the user closes the dashboard while ≥1
  download is in progress, a Windows toast balloon appears with the count.
- **Tray Quit pauses first** — The `Quit AsynxDL` menu pauses all running
  downloads to avoid orphan `.part*` chunks before destroying the root.
- **Heartbeat** — App mainloop schedules `TrayIcon.update_state()` every
  1.5 s so the tray reflects reality even after async `start()`.
- **Confirm dialog** — `confirm_dialog.py` module provides a reusable
  Yes/No modal with keyboard bindings (`Enter`/`Esc`). Wired into:
  - Pause (informational)
  - Delete (danger style)
  - Remove-from-history (danger style)
- **Remove-from-history button** — Visible only when status is `COMPLETED`,
  `ERROR`, or `CANCELLED`. Calls `PATCH /downloads/{id}/remove_history`.
- **Default card icon** — Replaced letter `"A"` placeholder with `📥` emoji
  on the sidebar and inside the download card.

### API surface
- `DELETE /downloads/{id}?delete_parts=&remove_from_history=` — new
  `remove_from_history` boolean lets the UI fully purge history in one call.
- `PATCH /downloads/{id}/remove_history?delete_parts=` — symmetric remove
  from `data/queue/completed/` and clean parts without touching the active
  queue.

### Tests (32 total, all PASS)
- **+16 new tests in v1.0.1**:
  - `test_filename_resolution.py` — 9 tests for `url_basename` and
    `resolve_filename` (percent-decoding, query-strip, fragment-strip,
    sanitisation, traversal defense, fallback).
  - `test_parts_dir.py` — 3 tests for the parts cleanup helper (hidden
    directory, cleanup, orphans cutoff).
  - `test_state_recovery.py` — 4 tests for `mark_completed`,
    `remove_from_history`, `list_history`, `list_all_with_history`.
- **+8 pre-existing v1.0.0 tests** continue to PASS (auth, downloads,
  pause/resume, chunk retry, metadata, validator).

## [1.0.0] — 2026-07-02

- Initial release. See README.md and `walkthrough.md` for details.
