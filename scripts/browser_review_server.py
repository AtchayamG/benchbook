"""LOCAL TEST ONLY: real HTTP/PG/SPA and actual Strands over fake HTTP.

Starts an owned disposable PostgreSQL cluster. No provider credentials/network.
The fake-provider quota override allows a complete workflow in one browser run.
Never use this entry point for deployment.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "services/repair_service/src"),
    str(ROOT / "services/repair_service/tests"),
]
os.environ.update(
    GROQ_API_KEY="",
    BENCHBOOK_GROQ_API_KEY="",
    BENCHBOOK_ASSISTANT_MODE="deterministic",
    BENCHBOOK_ENVIRONMENT="test",
)

if __name__ == "__main__":
    import uvicorn
    from disposable_postgres import DisposablePostgresCluster, find_pg_bin
    from test_strands_advisory import _make_mock_transport

    from benchbook.infrastructure import admission
    from benchbook.infrastructure.strands_advisory import StrandsAdvisoryEngine
    from benchbook.interfaces.http.app import create_app

    pg_bin = find_pg_bin()
    if not pg_bin:
        raise SystemExit("Local PostgreSQL binaries unavailable")
    cluster = DisposablePostgresCluster(pg_bin)
    try:
        cluster.start()
        database = cluster.create_isolated_db("browser_review")
        os.environ["BENCHBOOK_STATIC_DIR"] = str(ROOT / "apps/web/dist")
        app = create_app(database, "deterministic")

        class OfflineReviewEngine:
            async def generate_advice(self, **kwargs: Any) -> Any:
                engine = StrandsAdvisoryEngine(
                    app.state.admission_store,
                    api_key="offline-fixture-key",
                    transport=_make_mock_transport(),
                    mode="live",
                )
                return await engine.generate_advice(**kwargs)

        app.state.advisory_engine = OfflineReviewEngine()
        app.state.assistant_mode = "offline_transport_test"
        admission.GLOBAL_LIMIT_60S = 600
        admission.WORKSPACE_LIMIT_24H = 600
        admission.GLOBAL_LIMIT_24H = 600
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        output = ROOT / "output/playwright"
        output.mkdir(parents=True, exist_ok=True)
        (output / "review-url.txt").write_text(f"http://127.0.0.1:{port}", encoding="utf-8")
        print(f"OFFLINE_BROWSER_REVIEW http://127.0.0.1:{port}", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=port, access_log=False)
    finally:
        cluster.stop()
