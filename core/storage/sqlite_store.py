import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.models.models import CapabilityGrant, CapabilityType, GrantType

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

class SQLiteStore:
    def __init__(self, db_path: str = "rudi.db", encryption_key: Optional[str] = None):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cipher = Fernet(encryption_key.encode()) if encryption_key and Fernet else None
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        # Grants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grants (
                id TEXT PRIMARY KEY,
                agent_id TEXT,
                capability TEXT,
                scope TEXT,
                grant_type TEXT,
                risk_level TEXT,
                parent_id TEXT,
                constraints TEXT,
                expires_at TEXT,
                granted_at TEXT,
                last_used_at TEXT,
                metadata TEXT
            )
        """)
        # Migration: Add columns if missing (for existing DBs)
        cursor.execute("PRAGMA table_info(grants)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'parent_id' not in columns:
            cursor.execute("ALTER TABLE grants ADD COLUMN parent_id TEXT")
        if 'constraints' not in columns:
            cursor.execute("ALTER TABLE grants ADD COLUMN constraints TEXT")

        # Agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                token_hash TEXT,
                created_at TEXT
            )
        """)
        self.conn.commit()

    def _encrypt(self, data: str) -> str:
        if self.cipher:
            return self.cipher.encrypt(data.encode()).decode()
        return data

    def _decrypt(self, data: str) -> str:
        if self.cipher:
            return self.cipher.decrypt(data.encode()).decode()
        return data

    def save_grant(self, grant: CapabilityGrant):
        scope_json = json.dumps(grant.scope)
        encrypted_scope = self._encrypt(scope_json)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO grants (
                id, agent_id, capability, scope, grant_type, 
                risk_level, parent_id, constraints, expires_at, granted_at, last_used_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            grant.id,
            grant.agent_id,
            grant.capability,
            encrypted_scope,
            grant.grant_type.value,
            grant.risk_level,
            grant.parent_id,
            json.dumps(grant.constraints) if grant.constraints else None,
            grant.expires_at.isoformat() if grant.expires_at else None,
            grant.granted_at.isoformat(),
            grant.last_used_at.isoformat() if grant.last_used_at else None,
            json.dumps(grant.metadata)
        ))
        self.conn.commit()

    def delete_grant(self, grant_id: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM grants WHERE id = ?", (grant_id,))
        self.conn.commit()

    def load_all_grants(self) -> List[CapabilityGrant]:
        grants = []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM grants")
        for row in cursor.fetchall():
            expires_at = datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None
            granted_at = datetime.fromisoformat(row['granted_at'])
            last_used_at = datetime.fromisoformat(row['last_used_at']) if row['last_used_at'] else None
            
            try:
                decrypted_scope = self._decrypt(row['scope'])
                scope = json.loads(decrypted_scope)
            except Exception:
                continue
                
            grant = CapabilityGrant(
                id=row['id'],
                agent_id=row['agent_id'],
                capability=row['capability'],
                scope=scope,
                grant_type=GrantType(row['grant_type']),
                risk_level=row['risk_level'],
                parent_id=row['parent_id'],
                constraints=json.loads(row['constraints']) if row['constraints'] else None,
                expires_at=expires_at,
                granted_at=granted_at,
                last_used_at=last_used_at,
                metadata=json.loads(row['metadata'])
            )
            grants.append(grant)
        return grants

    def save_agent(self, agent_id: str, token_hash: str):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO agents (agent_id, token_hash, created_at)
            VALUES (?, ?, ?)
        """, (agent_id, token_hash, datetime.now().isoformat()))
        self.conn.commit()

    def get_all_agents(self) -> Dict[str, str]:
        agents = {}
        cursor = self.conn.cursor()
        cursor.execute("SELECT agent_id, token_hash FROM agents")
        for row in cursor.fetchall():
            agents[row['agent_id']] = row['token_hash']
        return agents

    def close(self):
        self.conn.close()
