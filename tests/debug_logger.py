import asyncio
import os
import json
from core.models.models import AuditEvent, CapabilityType
from core.audit.logger import AuditLogger
from core.audit.store import AuditStore

async def debug():
    log_path = "debug_audit.log"
    if os.path.exists(log_path): os.remove(log_path)
    
    logger = AuditLogger(log_path=log_path)
    event = AuditEvent(
        agent_id="test",
        event_type="request",
        action="test",
        resource="test",
        status="success"
    )
    logger.log_event(event)
    
    print(f"File exists: {os.path.exists(log_path)}")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            content = f.read()
            print(f"Content: '{content}'")
            
    store = AuditStore(log_path=log_path)
    metrics = store.get_metrics()
    print(f"Metrics: {metrics}")
    
    if os.path.exists(log_path): os.remove(log_path)

if __name__ == "__main__":
    asyncio.run(debug())
