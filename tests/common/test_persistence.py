import unittest
import os
from core.control_plane.manager import ControlPlaneManager
from core.models.models import CapabilityRequest, CapabilityType, GrantType, CapabilityGrant
from core.storage.sqlite_store import SQLiteStore
from uuid import uuid4
from datetime import datetime, timedelta

class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_rudi.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.config = {"db_path": self.test_db}
        self.storage = SQLiteStore(self.test_db)
        self.cp = ControlPlaneManager(self.config, storage=self.storage)

    def tearDown(self):
        self.cp.shutdown()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_grant_persistence(self):
        agent_id = "agent-persisted"
        grant_id = str(uuid4())
        grant = CapabilityGrant(
            id=grant_id,
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            grant_type=GrantType.SESSION,
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        with self.cp.lock:
            self.cp.grants[grant_id] = grant
            self.cp.storage.save_grant(grant)

        cp2 = ControlPlaneManager(self.config)
        self.assertIn(grant_id, cp2.grants)
        self.assertEqual(cp2.grants[grant_id].agent_id, agent_id)
        cp2.shutdown()

    def test_agent_persistence(self):
        agent_id = "agent-007"
        token = "bond-james-bond"
        self.cp.register_agent(agent_id, token)
        
        cp2 = ControlPlaneManager(self.config)
        self.cp.strict_identity = True
        cp2.strict_identity = True
        self.assertTrue(cp2._verify_agent(agent_id, token))
        self.assertFalse(cp2._verify_agent(agent_id, "wrong-token"))
        cp2.shutdown()

    def test_encryption_persistence(self):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        db_path = "test_encrypted.db"
        if os.path.exists(db_path): os.remove(db_path)
        
        store = SQLiteStore(db_path, encryption_key=key)
        agent_id = "agent-encrypted"
        grant_id = str(uuid4())
        grant = CapabilityGrant(
            id=grant_id,
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"secret_path": "/vault/key.txt"},
            grant_type=GrantType.SESSION
        )
        store.save_grant(grant)
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT scope FROM grants WHERE id = ?", (grant_id,))
        db_scope = cursor.fetchone()[0]
        self.assertNotIn("/vault/key.txt", db_scope)
        conn.close()
        
        store2 = SQLiteStore(db_path, encryption_key=key)
        loaded_grants = store2.load_all_grants()
        self.assertEqual(loaded_grants[0].scope["secret_path"], "/vault/key.txt")
        
        store.close()
        store2.close()
        if os.path.exists(db_path): os.remove(db_path)

if __name__ == "__main__":
    unittest.main()
