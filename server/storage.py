"""Local account creation and token authentication."""
from contextlib import closing
import hmac
from pathlib import Path
import secrets
import sqlite3

class Accounts:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, name TEXT NOT NULL DEFAULT 'Guest')")
            cols = {row[1] for row in db.execute('PRAGMA table_info(accounts)')}
            if 'name' not in cols:
                db.execute("ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT 'Guest'")
    def login(self, account_id, token):
        with closing(sqlite3.connect(self.path)) as db, db:
            if account_id == 0:
                token = secrets.token_hex(20)
                cur = db.execute('INSERT INTO accounts(token) VALUES (?)', (token,))
                return {'id': cur.lastrowid, 'token': token, 'name': 'Guest'}
            row = db.execute('SELECT token, name FROM accounts WHERE id=?', (account_id,)).fetchone()
            if row and token and hmac.compare_digest(row[0], token):
                return {'id': account_id, 'token': row[0], 'name': row[1]}
            return None

    def set_name(self, account_id, name):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE accounts SET name=? WHERE id=?', (name, account_id))
