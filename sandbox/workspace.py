"""Session workspace — each chat session gets its own isolated directory."""
from __future__ import annotations
import shutil
import uuid
from pathlib import Path
import config


class Workspace:
    """Ephemeral per-session sandbox directory."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.path = config.WORKSPACE_DIR / self.session_id
        self.path.mkdir(parents=True, exist_ok=True)

    def destroy(self):
        """Remove all files created during this session."""
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def list_files(self) -> list[str]:
        """Return relative paths of all files in the workspace."""
        return [
            str(p.relative_to(self.path))
            for p in self.path.rglob("*")
            if p.is_file() and not p.name.startswith("_")
        ]

    def __repr__(self) -> str:
        return f"Workspace(session_id={self.session_id!r}, path={self.path})"
