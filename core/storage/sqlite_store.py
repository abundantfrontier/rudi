import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.models.models import CapabilityGrant, CapabilityType, GrantType, DelegatedTask, Persona, Project, HistorySummary

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
                project_id TEXT,
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
        if 'project_id' not in columns:
            cursor.execute("ALTER TABLE grants ADD COLUMN project_id TEXT")

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                label TEXT,
                instruction TEXT,
                project_id TEXT,
                schedule_type TEXT,
                target_time TEXT,
                interval_seconds INTEGER,
                last_run_at TEXT,
                next_run_at TEXT,
                metadata TEXT
            )
        """)
        # Migration for tasks
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'project_id' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT")

        # Personas table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                metadata TEXT
            )
        """)

        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                persona_id TEXT,
                name TEXT,
                description TEXT,
                metadata TEXT
            )
        """)

        # History Summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history_summaries (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                agent_id TEXT,
                timestamp TEXT,
                summary TEXT,
                content_hash TEXT,
                metadata TEXT
            )
        """)

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
                risk_level, parent_id, constraints, project_id, expires_at, granted_at, last_used_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            grant.id,
            grant.agent_id,
            grant.capability,
            encrypted_scope,
            grant.grant_type.value,
            grant.risk_level,
            grant.parent_id,
            json.dumps(grant.constraints) if grant.constraints else None,
            grant.project_id,
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
                project_id=row['project_id'],
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

    def save_task(self, task: DelegatedTask):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tasks (
                id, label, instruction, project_id, schedule_type, target_time, 
                interval_seconds, last_run_at, next_run_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id,
            task.label,
            task.instruction,
            task.project_id,
            task.schedule_type,
            task.target_time.isoformat() if task.target_time else None,
            task.interval_seconds,
            task.last_run_at.isoformat() if task.last_run_at else None,
            task.next_run_at.isoformat() if task.next_run_at else None,
            json.dumps(task.metadata)
        ))
        self.conn.commit()

    def delete_task(self, task_id: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def load_all_tasks(self) -> List[DelegatedTask]:
        tasks = []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        for row in cursor.fetchall():
            target_time = datetime.fromisoformat(row['target_time']) if row['target_time'] else None
            last_run_at = datetime.fromisoformat(row['last_run_at']) if row['last_run_at'] else None
            next_run_at = datetime.fromisoformat(row['next_run_at']) if row['next_run_at'] else None
            
            task = DelegatedTask(
                id=row['id'],
                label=row['label'],
                instruction=row['instruction'],
                project_id=row['project_id'],
                schedule_type=row['schedule_type'],
                target_time=target_time,
                interval_seconds=row['interval_seconds'],
                last_run_at=last_run_at,
                next_run_at=next_run_at,
                metadata=json.loads(row['metadata'])
            )
            tasks.append(task)
        return tasks

    # --- Persona CRUD ---
    def save_persona(self, persona: Persona):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO personas (id, name, description, metadata)
            VALUES (?, ?, ?, ?)
        """, (persona.id, persona.name, persona.description, json.dumps(persona.metadata)))
        self.conn.commit()

    def load_all_personas(self) -> List[Persona]:
        personas = []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM personas")
        for row in cursor.fetchall():
            personas.append(Persona(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                metadata=json.loads(row['metadata'])
            ))
        return personas

    # --- Project CRUD ---
    def save_project(self, project: Project):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO projects (id, persona_id, name, description, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (project.id, project.persona_id, project.name, project.description, json.dumps(project.metadata)))
        self.conn.commit()

    def load_projects(self, persona_id: Optional[str] = None) -> List[Project]:
        projects = []
        cursor = self.conn.cursor()
        if persona_id:
            cursor.execute("SELECT * FROM projects WHERE persona_id = ?", (persona_id,))
        else:
            cursor.execute("SELECT * FROM projects")
        for row in cursor.fetchall():
            projects.append(Project(
                id=row['id'],
                persona_id=row['persona_id'],
                name=row['name'],
                description=row['description'],
                metadata=json.loads(row['metadata'])
            ))
        return projects

    # --- History Summary CRUD ---
    def save_history_summary(self, summary: HistorySummary):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO history_summaries (
                id, project_id, agent_id, timestamp, summary, content_hash, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.id, summary.project_id, summary.agent_id, 
            summary.timestamp.isoformat(), summary.summary, 
            summary.content_hash, json.dumps(summary.metadata)
        ))
        self.conn.commit()

    def query_history(self, project_id: str, query: Optional[str] = None, limit: int = 50) -> List[HistorySummary]:
        results = []
        cursor = self.conn.cursor()
        if query:
            # Simple keyword match for now
            cursor.execute("""
                SELECT * FROM history_summaries 
                WHERE project_id = ? AND summary LIKE ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (project_id, f"%{query}%", limit))
        else:
            cursor.execute("""
                SELECT * FROM history_summaries 
                WHERE project_id = ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (project_id, limit))
        
        for row in cursor.fetchall():
            results.append(HistorySummary(
                id=row['id'],
                project_id=row['project_id'],
                agent_id=row['agent_id'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                summary=row['summary'],
                content_hash=row['content_hash'],
                metadata=json.loads(row['metadata'])
            ))
        return results
