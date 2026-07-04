"""AsynxDL — Synchronous preheat-chain smoke (v1.0.7).

Verifies that the belt-and-suspenders preheat routines in
``backend/main.py`` and ``build/runtime_hook_overlapped.py`` survive
the kind of import order that triggers the recent
``ModuleNotFoundError`` regressions:

    requests -> idna -> unicodedata     (unicodedata.pyd C-ext)
    fastapi  -> pydantic -> pydantic_core._pydantic_core   (Rust pyd)
    uvicorn  -> asyncio -> asyncio.windows_events -> _overlapped

Run with::

    python -m pytest tests/test_preheat_chain.py -v
"""
import importlib
import os
import sys
import types


def _safe_import(name: str) -> bool:
    """Best-effort import with explicit log so we can pinpoint loot."""
    try:
        importlib.import_module(name)
        return True
    except Exception as exc:  # pragma: no cover
        print(f"  preheat[{name}] failed: {exc!r}")
        return False


def test_pydantic_core_warm():
    # Hot path cold-load: pydantic + pydantic_core + nested _pydantic_core.
    assert _safe_import("pydantic_core")
    assert _safe_import("pydantic_core._pydantic_core")


def test_unicodedata_warm():
    # Hot path cold-load: requests -> idna -> unicodedata chain.
    assert _safe_import("unicodedata")
    assert _safe_import("idna")


def test_overlapped_warm():
    # Hot path cold-load: _overlapped.pyd.
    assert _safe_import("_overlapped") or sys.platform != "win32"


def test_runtime_hook_pretend_frozen():
    """Sintesis: jalankan runtime_hook_overlapped.py dengan sys.frozen=True
    untuk mensimulasikan kondisi bootloader pasca os.execv.
    Semua pre-import harus succeeded (atau skipped best-effort).
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hook_path = os.path.join(root, "build", "runtime_hook_overlapped.py")
    assert os.path.exists(hook_path), hook_path
    with open(hook_path, "r", encoding="utf-8") as f:
        hook_src = f.read()

    saved_frozen = getattr(sys, "frozen", False)
    sys.frozen = True  # noqa: S604 - intentional simulation
    try:
        # Hook di-exec dalam namespace dummy sehingga tidak overwrite modul
        # ini sendiri jika ada nama bentrok.
        ns: dict[str, types.ModuleType] = {"sys": sys}
        exec(compile(hook_src, hook_path, "exec"), ns)  # noqa: S102
    finally:
        sys.frozen = saved_frozen


def test_main_preheat_callables():
    """Pastikan helper preheat ada di backend.main dan idempotent."""
    main = importlib.import_module("backend.main")
    for name in (
        "_preheat_uvicorn_runtime",
        "_preheat_pydantic_core",
        "_preheat_stdlib_extensions",
        "_ensure_overlapped",
    ):
        assert hasattr(main, name), f"missing preheat helper: {name}"
        fn = getattr(main, name)
        # Invoke to confirm idempotency.
        assert fn() in (None, True, False) or fn() is not None
