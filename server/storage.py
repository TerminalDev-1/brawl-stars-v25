"""Local account creation and token authentication."""
from contextlib import closing
import hmac
from pathlib import Path
import secrets
import sqlite3
import uuid

class Accounts:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, name TEXT NOT NULL DEFAULT 'Guest')")
            cols = {row[1] for row in db.execute('PRAGMA table_info(accounts)')}
            if 'name' not in cols:
                db.execute("ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT 'Guest'")
            for column in ('tokens', 'trophies'):
                if column not in cols:
                    db.execute(f"ALTER TABLE accounts ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
            db.execute("CREATE TABLE IF NOT EXISTS battles (id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, status TEXT NOT NULL, reward INTEGER NOT NULL DEFAULT 0)")
    def login(self, account_id, token):
        with closing(sqlite3.connect(self.path)) as db, db:
            if account_id == 0:
                token = secrets.token_hex(20)
                cur = db.execute('INSERT INTO accounts(token) VALUES (?)', (token,))
                return {'id': cur.lastrowid, 'token': token, 'name': 'Guest', 'tokens': 0, 'trophies': 0}
            row = db.execute('SELECT token, name, tokens, trophies FROM accounts WHERE id=?', (account_id,)).fetchone()
            if row and token and hmac.compare_digest(row[0], token):
                return {'id': account_id, 'token': row[0], 'name': row[1], 'tokens': row[2], 'trophies': row[3]}
            return None

    def set_name(self, account_id, name):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE accounts SET name=? WHERE id=?', (name, account_id))

    def begin_battle(self, account_id):
        match_id = uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO battles(id, account_id, status) VALUES (?, ?, 'active')", (match_id, account_id))
        return match_id

    def complete_battle(self, account_id, match_id, result):
        # Gem Grab rewards; only a completed, active match can award tokens.
        if result not in (0, 1, 2):
            raise ValueError('invalid battle result')
        reward = (20, 10, 15)[result]
        trophy_delta = (8, 0, 0)[result]
        with closing(sqlite3.connect(self.path)) as db, db:
            changed = db.execute("UPDATE battles SET status='complete', reward=? WHERE id=? AND account_id=? AND status='active'", (reward, match_id, account_id)).rowcount
            if not changed:
                return None
            db.execute('UPDATE accounts SET tokens=tokens+?, trophies=trophies+? WHERE id=?', (reward, trophy_delta, account_id))
            tokens, trophies = db.execute('SELECT tokens, trophies FROM accounts WHERE id=?', (account_id,)).fetchone()
            return {'tokens': tokens, 'trophies': trophies, 'reward': reward, 'trophy_delta': trophy_delta}

    def abandon_battle(self, account_id, match_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE battles SET status='abandoned' WHERE id=? AND account_id=? AND status='active'", (match_id, account_id))
