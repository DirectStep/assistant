import asyncio
import logging
import time
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)


async def cleanup_job(settings: Settings) -> int:
    return await asyncio.to_thread(_remove_stale_temporary_pdfs, settings.digest_output_dir)


def _remove_stale_temporary_pdfs(output_dir: Path, max_age_seconds: int = 86_400) -> int:
    directory = output_dir.resolve()
    if not directory.is_dir():
        return 0
    cutoff = time.time() - max_age_seconds
    removed = 0
    for path in directory.glob("*.tmp.pdf"):
        resolved = path.resolve()
        if resolved.parent != directory or resolved.stat().st_mtime >= cutoff:
            continue
        resolved.unlink()
        removed += 1
    if removed:
        logger.info("Removed stale temporary PDFs", extra={"removed_count": removed})
    return removed
