import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'healthcare_platform.db')

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    changes = []

    cursor.execute('PRAGMA table_info(integration_operations)')
    io_cols = [row[1] for row in cursor.fetchall()]
    if 'hospital_id' not in io_cols:
        cursor.execute('ALTER TABLE integration_operations ADD COLUMN hospital_id INTEGER')
        changes.append('integration_operations.hospital_id')

    cursor.execute('PRAGMA table_info(workflow_executions)')
    wf_cols = [row[1] for row in cursor.fetchall()]
    if 'idempotency_key' not in wf_cols:
        cursor.execute('ALTER TABLE workflow_executions ADD COLUMN idempotency_key VARCHAR(100)')
        changes.append('workflow_executions.idempotency_key')
    if 'correlation_id' not in wf_cols:
        cursor.execute('ALTER TABLE workflow_executions ADD COLUMN correlation_id VARCHAR(100)')
        changes.append('workflow_executions.correlation_id')

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointment_state_history'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE appointment_state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                from_status VARCHAR(50),
                to_status VARCHAR(50) NOT NULL,
                reason VARCHAR(255),
                actor VARCHAR(255),
                correlation_id VARCHAR(100) NOT NULL,
                created_at DATETIME
            )
        ''')
        cursor.execute('CREATE INDEX ix_ash_appointment_id ON appointment_state_history (appointment_id)')
        cursor.execute('CREATE INDEX ix_ash_correlation_id ON appointment_state_history (correlation_id)')
        changes.append('CREATE TABLE appointment_state_history')

    conn.commit()
    conn.close()

    if changes:
        print('Applied migrations:')
        for c in changes:
            print('  +', c)
    else:
        print('No migrations needed.')

run_migration()
