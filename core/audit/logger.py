import json
import logging
import logging.handlers
import os
from core.models.models import AuditEvent

class AuditLogger:
    """
    Handles structured audit logging for all R.U.D.I. events.
    Uses RotatingFileHandler and pure JSONL format for production readiness.
    Ensures data durability on disk via os.fsync.
    """
    def __init__(self, log_path: str = "audit.log", max_bytes: int = 10*1024*1024, backup_count: int = 5):
        self.log_path = log_path
        self.logger = logging.getLogger(f"rudi_audit_{hash(log_path)}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.handlers.RotatingFileHandler(
                self.log_path, 
                maxBytes=max_bytes, 
                backupCount=backup_count
            )
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_event(self, event: AuditEvent):
        """
        Append an audit event to the log and ensure it is written to disk.
        """
        self.logger.info(event.model_dump_json())
        # Force flush and sync for 100% durability
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.flush()
                try:
                    os.fsync(handler.stream.fileno())
                except (AttributeError, ValueError, OSError):
                    pass
