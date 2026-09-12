"""Disposable PostgreSQL cluster management for test suites."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

# Path to reusable local PG 16.10 binaries on this machine
_DEFAULT_PG_BIN = (
    Path(__file__).resolve().parents[4]
    / "00_PROGRAM_CONTROL"
    / "worktrees"
    / "BS-011-claude"
    / ".pgtest"
    / "pgsql"
    / "bin"
)


def find_pg_bin() -> Path | None:
    """Locate PostgreSQL binary directory."""
    env_path = os.environ.get("BENCHBOOK_PG_BIN")
    if env_path and (Path(env_path) / "postgres.exe").exists():
        return Path(env_path)

    if (_DEFAULT_PG_BIN / "postgres.exe").exists():
        return _DEFAULT_PG_BIN

    sys_postgres = shutil.which("postgres")
    if sys_postgres:
        return Path(sys_postgres).parent

    return None


def get_ephemeral_port() -> int:
    """Find an available loopback port assigned by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def wait_for_port(
    port: int, open_target: bool, timeout_s: float = 15.0, host: str = "127.0.0.1"
) -> bool:
    """Poll a port until it reaches open_target status or times out."""
    start = time.time()
    while time.time() - start < timeout_s:
        if is_port_open(port, host) == open_target:
            return True
        time.sleep(0.15)
    return False


class DisposablePostgresCluster:
    """Manages an ephemeral, isolated PostgreSQL 16 server on localhost."""

    def __init__(self, pg_bin: Path, root_dir: Path | None = None) -> None:
        self.pg_bin = pg_bin
        repo_root = Path(__file__).resolve().parents[3]
        test_root = (repo_root / "test-results").resolve()
        test_root.mkdir(parents=True, exist_ok=True)
        self.root_dir = Path(tempfile.mkdtemp(prefix="pg-review-", dir=test_root))
        if root_dir is not None:
            raise ValueError("Disposable clusters must use a unique owned test directory")
        self.data_dir = self.root_dir / "data"
        self.log_file = self.root_dir / "server.log"
        self.port = get_ephemeral_port()
        self.base_url = f"postgresql://postgres@127.0.0.1:{self.port}/postgres"
        self._started = False

    def start(self) -> None:
        """Initialize and start the ephemeral cluster."""
        self.root_dir.mkdir(parents=True, exist_ok=True)

        # Run initdb
        initdb_cmd = [
            str(self.pg_bin / "initdb.exe"),
            "-D",
            str(self.data_dir),
            "-U",
            "postgres",
            "-E",
            "UTF8",
            "--auth-local=trust",
            "--auth-host=trust",
        ]
        subprocess.run(
            initdb_cmd,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
        )

        # Append configuration
        conf_path = self.data_dir / "postgresql.conf"
        with open(conf_path, "a", encoding="utf-8") as f:
            f.write(
                f"\nlisten_addresses = '127.0.0.1'\n"
                f"port = {self.port}\n"
                f"max_connections = 60\n"
                f"shared_buffers = 32MB\n"
                f"fsync = on\n"
                f"synchronous_commit = on\n"
            )

        # Start via pg_ctl
        start_cmd = [
            str(self.pg_bin / "pg_ctl.exe"),
            "-D",
            str(self.data_dir),
            "-l",
            str(self.log_file),
            "start",
            "-w",
            "-t",
            "20",
        ]
        subprocess.run(
            start_cmd,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

        self._started = True
        if not wait_for_port(self.port, True, timeout_s=15.0):
            raise RuntimeError(
                f"PostgreSQL cluster failed to start on port {self.port} within timeout"
            )

    def create_isolated_db(self, name_prefix: str = "test") -> str:
        """Create a fresh isolated database and return its connection DSN."""
        if not self._started:
            raise RuntimeError("Postgres cluster is not started")

        import psycopg

        unique_id = uuid.uuid4().hex[:8]
        db_name = f"{name_prefix}_{unique_id}".lower()

        with (
            psycopg.connect(self.base_url, autocommit=True, connect_timeout=5) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(f'CREATE DATABASE "{db_name}"')

        return f"postgresql://postgres@127.0.0.1:{self.port}/{db_name}"

    def stop(self) -> None:
        """Stop our PostgreSQL server; retain its isolated files for diagnosis."""
        if not self._started:
            return

        stop_cmd = [
            str(self.pg_bin / "pg_ctl.exe"),
            "-D",
            str(self.data_dir),
            "-m",
            "fast",
            "stop",
            "-w",
            "-t",
            "15",
        ]
        subprocess.run(
            stop_cmd,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        if not wait_for_port(self.port, False, timeout_s=10.0):
            raise RuntimeError("Owned PostgreSQL server did not stop")
        self._started = False
