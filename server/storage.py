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
            for column in ('tokens', 'trophies', 'highest_trophies', 'experience'):
                if column not in cols:
                    db.execute(f"ALTER TABLE accounts ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
            # Trophies have never dropped so far, so existing accounts start with highest = current.
            db.execute('UPDATE accounts SET highest_trophies=trophies WHERE highest_trophies<trophies')
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

    def complete_battle(self, account_id, match_id, reward, trophy_delta, experience_gain):
        """Apply one battle's rewards; only a completed, active match can award them."""
        if reward < 0 or experience_gain < 0:
            raise ValueError('invalid battle reward')
        with closing(sqlite3.connect(self.path)) as db, db:
            changed = db.execute("UPDATE battles SET status='complete', reward=? WHERE id=? AND account_id=? AND status='active'", (reward, match_id, account_id)).rowcount
            if not changed:
                return None
            before = db.execute('SELECT trophies, highest_trophies, experience FROM accounts WHERE id=?', (account_id,)).fetchone()
            # Trophies never drop below zero.
            trophy_delta = max(trophy_delta, -before[0])
            db.execute('UPDATE accounts SET tokens=tokens+?, trophies=trophies+?, highest_trophies=MAX(highest_trophies, trophies+?), experience=experience+? WHERE id=?',
                       (reward, trophy_delta, trophy_delta, experience_gain, account_id))
            tokens, trophies = db.execute('SELECT tokens, trophies FROM accounts WHERE id=?', (account_id,)).fetchone()
            return {'tokens': tokens, 'trophies': trophies, 'reward': reward, 'trophy_delta': trophy_delta,
                    'old_trophies': before[0], 'old_highest_trophies': before[1],
                    'old_experience': before[2], 'experience_gain': experience_gain}

    def abandon_battle(self, account_id, match_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE battles SET status='abandoned' WHERE id=? AND account_id=? AND status='active'", (match_id, account_id))
