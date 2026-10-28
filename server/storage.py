"""Local account creation and token authentication."""
from contextlib import closing
import hmac
from pathlib import Path
import secrets
import sqlite3
import uuid
from brawlers import OWNED_BRAWLERS, SHELLY

class Accounts:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, name TEXT NOT NULL DEFAULT 'Guest')")
            cols = {row[1] for row in db.execute('PRAGMA table_info(accounts)')}
            if 'name' not in cols:
                db.execute("ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT 'Guest'")
            for column in ('tokens', 'trophies', 'highest_trophies', 'experience', 'star_tokens', 'selected_brawler'):
                if column not in cols:
                    db.execute(f"ALTER TABLE accounts ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
            # Trophies have never dropped so far, so existing accounts start with highest = current.
            db.execute('UPDATE accounts SET highest_trophies=trophies WHERE highest_trophies<trophies')
            # Per-brawler trophies; the account total is their sum. Accounts from
            # before this table only ever played Shelly.
            db.execute('CREATE TABLE IF NOT EXISTS brawlers (account_id INTEGER NOT NULL, brawler INTEGER NOT NULL, trophies INTEGER NOT NULL DEFAULT 0, highest INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (account_id, brawler))')
            db.execute('INSERT OR IGNORE INTO brawlers(account_id, brawler, trophies, highest) SELECT id, ?, trophies, highest_trophies FROM accounts '
                       'WHERE NOT EXISTS (SELECT 1 FROM brawlers WHERE account_id=accounts.id)', (SHELLY,))
            db.execute("CREATE TABLE IF NOT EXISTS battles (id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, status TEXT NOT NULL, reward INTEGER NOT NULL DEFAULT 0)")
    def login(self, account_id, token):
        with closing(sqlite3.connect(self.path)) as db, db:
            if account_id == 0:
                token = secrets.token_hex(20)
                account_id = db.execute('INSERT INTO accounts(token) VALUES (?)', (token,)).lastrowid
            else:
                row = db.execute('SELECT token FROM accounts WHERE id=?', (account_id,)).fetchone()
                if not (row and token and hmac.compare_digest(row[0], token)):
                    return None
            return self._player(db, account_id)

    def _player(self, db, account_id):
        row = db.execute('SELECT token, name, tokens, trophies, highest_trophies, star_tokens, selected_brawler FROM accounts WHERE id=?', (account_id,)).fetchone()
        brawlers = {b: (0, 0) for b in OWNED_BRAWLERS}
        for brawler, trophies, highest in db.execute('SELECT brawler, trophies, highest FROM brawlers WHERE account_id=?', (account_id,)):
            if brawler in brawlers:
                brawlers[brawler] = (trophies, highest)
        selected = row[6] if row[6] in OWNED_BRAWLERS else SHELLY
        return {'id': account_id, 'token': row[0], 'name': row[1], 'tokens': row[2], 'trophies': row[3],
                'highest_trophies': row[4], 'star_tokens': row[5], 'selected_brawler': selected, 'brawlers': brawlers}

    def set_name(self, account_id, name):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE accounts SET name=? WHERE id=?', (name, account_id))

    def begin_battle(self, account_id):
        match_id = uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO battles(id, account_id, status) VALUES (?, ?, 'active')", (match_id, account_id))
        return match_id

    def complete_battle(self, account_id, match_id, brawler, reward, trophy_delta, experience_gain, star_token_gain=0):
        """Apply one battle's rewards; only a completed, active match can award them."""
        if reward < 0 or experience_gain < 0 or star_token_gain < 0 or brawler not in OWNED_BRAWLERS:
            raise ValueError('invalid battle reward')
        with closing(sqlite3.connect(self.path)) as db, db:
            changed = db.execute("UPDATE battles SET status='complete', reward=? WHERE id=? AND account_id=? AND status='active'", (reward, match_id, account_id)).rowcount
            if not changed:
                return None
            experience = db.execute('SELECT experience FROM accounts WHERE id=?', (account_id,)).fetchone()[0]
            db.execute('INSERT OR IGNORE INTO brawlers(account_id, brawler) VALUES (?, ?)', (account_id, brawler))
            old_trophies, old_highest = db.execute('SELECT trophies, highest FROM brawlers WHERE account_id=? AND brawler=?', (account_id, brawler)).fetchone()
            # A brawler's trophies never drop below zero.
            trophy_delta = max(trophy_delta, -old_trophies)
            db.execute('UPDATE brawlers SET trophies=trophies+?, highest=MAX(highest, trophies+?) WHERE account_id=? AND brawler=?',
                       (trophy_delta, trophy_delta, account_id, brawler))
            db.execute('UPDATE accounts SET tokens=tokens+?, trophies=trophies+?, highest_trophies=MAX(highest_trophies, trophies+?), experience=experience+?, star_tokens=star_tokens+?, selected_brawler=? WHERE id=?',
                       (reward, trophy_delta, trophy_delta, experience_gain, star_token_gain, brawler, account_id))
            player = self._player(db, account_id)
            return {'player': player, 'tokens': player['tokens'], 'trophies': player['trophies'], 'star_tokens': player['star_tokens'],
                    'reward': reward, 'trophy_delta': trophy_delta, 'star_token_gain': star_token_gain,
                    'old_trophies': old_trophies, 'old_highest_trophies': old_highest,
                    'old_experience': experience, 'experience_gain': experience_gain}

    def abandon_battle(self, account_id, match_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE battles SET status='abandoned' WHERE id=? AND account_id=? AND status='active'", (match_id, account_id))
