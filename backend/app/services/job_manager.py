import time
import uuid
import threading
from typing import Optional, Dict, Any
from app.models.content_model import StructuredContentModel

class JobStatus:
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobManager:
    """Thread-safe in-memory manager for background analysis jobs."""

    def __init__(self, max_retention_seconds: float = 3600.0):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._max_retention_seconds = max_retention_seconds

    def create_job(self) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._cleanup_expired_locked(now)
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": JobStatus.PROCESSING,
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return dict(job)

    def set_progress(self, job_id: str, progress_message: str) -> bool:
        now = time.time()
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._jobs[job_id]["progress_message"] = progress_message
            self._jobs[job_id]["updated_at"] = now
            return True

    def set_completed(self, job_id: str, result: Any) -> bool:
        now = time.time()
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._jobs[job_id]["status"] = JobStatus.COMPLETED
            self._jobs[job_id]["result"] = result
            self._jobs[job_id]["updated_at"] = now
            return True

    def set_failed(self, job_id: str, error: str) -> bool:
        now = time.time()
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._jobs[job_id]["status"] = JobStatus.FAILED
            self._jobs[job_id]["error"] = error
            self._jobs[job_id]["updated_at"] = now
            return True

    def _cleanup_expired_locked(self, now: float) -> None:
        """Removes expired jobs to prevent memory leaks."""
        expired_ids = [
            jid for jid, data in self._jobs.items()
            if now - data.get("created_at", now) > self._max_retention_seconds
        ]
        for jid in expired_ids:
            self._jobs.pop(jid, None)

    def clear(self) -> None:
        """Clears all jobs (primarily for testing)."""
        with self._lock:
            self._jobs.clear()

# Global singleton instance
job_manager = JobManager()

def get_job_manager() -> JobManager:
    return job_manager
