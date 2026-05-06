import json
import os
from typing import List, Dict, Any, Optional
from core.models.models import AuditEvent

class AuditStore:
    def __init__(self, log_path: str = "audit.log"):
        self.log_path = log_path

    def query(self, 
              agent_id: Optional[str] = None, 
              event_type: Optional[str] = None, 
              status: Optional[str] = None,
              limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query the audit log. 
        Returns a list of raw event dicts (latest first).
        """
        if not os.path.exists(self.log_path):
            return []

        results = []
        with open(self.log_path, 'r') as f:
            lines = f.readlines()
            # Process in reverse to get latest first
            for line in reversed(lines):
                if len(results) >= limit:
                    break
                
                try:
                    # Log format is "YYYY-MM-DD HH:MM:SS,ms - {json}"
                    parts = line.split(" - ", 1)
                    if len(parts) < 2:
                        continue
                    
                    event_data = json.loads(parts[1])
                    
                    # Filtering
                    if agent_id and event_data.get("agent_id") != agent_id:
                        continue
                    if event_type and event_data.get("event_type") != event_type:
                        continue
                    if status and event_data.get("status") != status:
                        continue
                    
                    results.append(event_data)
                except (json.JSONDecodeError, IndexError):
                    continue
        
        return results

    def get_metrics(self) -> Dict[str, int]:
        """Return basic usage counters."""
        events = self.query(limit=1000)
        metrics = {
            "total_events": len(events),
            "grants": 0,
            "blocks": 0,
            "expirations": 0,
            "denials": 0
        }
        for e in events:
            etype = e.get("event_type")
            status = e.get("status")
            if etype == "grant": metrics["grants"] += 1
            if etype == "use" and status == "blocked": metrics["blocks"] += 1
            if etype == "expiration": metrics["expirations"] += 1
            if etype == "denial": metrics["denials"] += 1
        
        return metrics
