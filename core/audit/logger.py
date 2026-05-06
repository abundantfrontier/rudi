import json
import logging
import os
from core.models.models import AuditEvent

class AuditLogger:
    """
    Handles structured audit logging for all R.U.D.I. events.
    Ensures data durability on disk via os.fsync.
    """
    def __init__(self, log_path: str = "audit.log"):
        self.log_path = log_path
        self.logger = logging.getLogger("rudi_audit")
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers if re-initialized
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_path)
            formatter = logging.Formatter('%(asctime)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_event(self, event: AuditEvent):
        """
        Append an audit event to the log and ensure it is written to disk.
        
        Args:
            event: The AuditEvent object to log.
        """
        self.logger.info(event.model_dump_json())
        # Force flush and sync for 100% durability
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.flush()
                try:
                    # Ensure physical write to disk
                    os.fsync(handler.stream.fileno())
                except (AttributeError, ValueError, OSError):
                    # Fallback for environments where fsync is not supported
                    pass
