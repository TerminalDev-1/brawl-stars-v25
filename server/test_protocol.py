import asyncio
from contextlib import closing
import sqlite3
import unittest
import tempfile
from pathlib import Path
from storage import Accounts
from battles import read_result, result_message
from unittest.mock import patch
from protocol import Reader, Writer, packet, read_packet
from app import decode_login, client

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_battle_lifecycle_over_tcp(self):
        payload = bytes.fromhex('0001000f070610001d00010100000003596f751004000000000000013110120000000000000132101300000000000001331003000100000000013410080001000000000135')
        with tempfile.TemporaryDirectory() as tmp:
            store = Accounts(Path(tmp) / 'accounts.sqlite3')
            with patch('app.accounts', store):
                server = await asyncio.start_server(client, '127.0.0.1', 0)
                async with server:
                    reader, writer = await asyncio.open_connection(*server.sockets[0].getsockname())
                    body = Writer().integer(0).integer(0).string().integer(25).integer(0).integer(107).string('hash').bytes()
                    writer.write(packet(10101, body)); await writer.drain()
                    _, _, response = await read_packet(reader)
                    account_id = Reader(response).take(8)
                    account_id = int.from_bytes(account_id[4:], 'big')
                    await read_packet(reader)
                    writer.write(packet(14103) + packet(14110, payload)); await writer.drain()
                    self.assertEqual((await asyncio.wait_for(read_packet(reader), 2))[0], 23456)
                    writer.write(packet(14110, payload) + packet(14109)); await writer.drain()
                    self.assertEqual((await asyncio.wait_for(read_packet(reader), 2))[0], 24101)
                    with closing(sqlite3.connect(store.path)) as db:
                        self.assertEqual(db.execute('SELECT tokens FROM accounts WHERE id=?', (account_id,)).fetchone()[0], 20)
                    writer.close(); await writer.wait_closed()

    async def test_fragmented_packet(self):
        reader = asyncio.StreamReader()
        data = packet(10108, b'hello', 3)
        for b in data:
            reader.feed_data(bytes([b]))
        self.assertEqual(await read_packet(reader), (10108, 3, b'hello'))

    async def test_keepalive_over_tcp(self):
        server = await asyncio.start_server(client, '127.0.0.1', 0)
        async with server:
            reader, writer = await asyncio.open_connection(*server.sockets[0].getsockname())
            writer.write(packet(10108)); await writer.drain()
            self.assertEqual(await asyncio.wait_for(read_packet(reader), 2), (20108, 0, b''))
            writer.close(); await writer.wait_closed()

    async def test_create_login_and_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Accounts(Path(tmp) / 'accounts.sqlite3')
            with patch('app.accounts', store):
                server = await asyncio.start_server(client, '127.0.0.1', 0)
                async with server:
                    async def exchange(account_id, token):
                        reader, writer = await asyncio.open_connection(*server.sockets[0].getsockname())
                        body = Writer().integer(0).integer(account_id).string(token).integer(25).integer(0).integer(107).string('hash').bytes()
                        writer.write(packet(10101, body)); await writer.drain()
                        return reader, writer
                    reader, writer = await exchange(0, None)
                    kind, version, body = await asyncio.wait_for(read_packet(reader), 2)
                    self.assertEqual((kind, version), (20104, 1))
                    r = Reader(body)
                    self.assertEqual(r.integer(), 0)
                    account_id = r.integer()
                    self.assertEqual((r.integer(), r.integer()), (0, account_id))
                    token = r.string()
                    self.assertEqual((await read_packet(reader))[0], 24101)
                    writer.write(packet(10212, Writer().string('Dev').vint(7).bytes())); await writer.drain()
                    kind, _, body = await read_packet(reader)
                    self.assertEqual(kind, 24111)
                    response = Reader(body)
                    self.assertEqual((response.vint(), response.string(), response.vint()), (201, 'Dev', 7))
                    writer.close(); await writer.wait_closed()
                    reader, writer = await exchange(account_id, token)
                    self.assertEqual((await read_packet(reader))[0], 20104)
                    self.assertEqual((await read_packet(reader))[0], 24101)
                    self.assertEqual(store.login(account_id, token)['name'], 'Dev')
                    writer.close(); await writer.wait_closed()
                    reader, writer = await exchange(account_id, 'bad-token')
                    self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
                    writer.close(); await writer.wait_closed()

    def test_battle_result_wire_format(self):
        # Native v25 Gem Grab result with one player and five bots.
        payload = bytes.fromhex('0001000f070610001d00010100000003596f751004000000000000013110120000000000000132101300000000000001331003000100000000013410080001000000000135')
        outcome, roster = read_result(payload)
        self.assertEqual(outcome, 0)
        self.assertEqual(len(roster), 6)
        self.assertEqual(sum(p['local'] for p in roster), 1)
        progress = {'reward': 20, 'trophy_delta': 8, 'old_trophies': 8, 'old_highest_trophies': 8,
                    'old_experience': 16, 'experience_gain': 8}
        encoded = result_message({'id': 1, 'name': 'Test'}, roster, 0, progress)
        r = Reader(encoded)
        self.assertEqual([r.vint() for _ in range(16)], [0, 0, 20, 8] + [0] * 12)
        r.take(2)
        self.assertEqual(r.vint(), 6)
        for p in roster:
            r.take(1)
            self.assertEqual((r.vint(), r.vint()), (16, p['brawler']))
            if r.vint():
                r.vint()
            self.assertEqual([r.vint() for _ in range(3)], [8 if p['local'] else 0, 0, 1])
            if r.take(1)[0]:
                r.integer(); r.integer()
            r.string(); [r.vint() for _ in range(3)]
        # Reward pairs, reward references, then the rank and experience bars.
        self.assertEqual([r.vint() for _ in range(3)], [1, 0, 8])
        self.assertEqual(r.vint(), 0)
        self.assertEqual([r.vint() for _ in range(7)], [2, 1, 8, 8, 5, 16, 16])
        self.assertEqual((r.vint(), r.take(1)), (0, b'\x00'))
        self.assertEqual(r.offset, len(encoded))
        with self.assertRaises(ValueError):
            read_result(payload[:-1])
        # The client's second and third header values vary between matches.
        self.assertEqual(read_result(bytes.fromhex('0002') + payload[2:])[0], 0)

    def test_battle_rewards_are_persistent_and_once_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Accounts(Path(tmp) / 'accounts.sqlite3')
            player = store.login(0, None)
            match = store.begin_battle(player['id'])
            self.assertEqual(store.complete_battle(player['id'], match, 0)['tokens'], 20)
            self.assertIsNone(store.complete_battle(player['id'], match, 0))
            restored = store.login(player['id'], player['token'])
            self.assertEqual((restored['tokens'], restored['trophies']), (20, 8))
            second = store.complete_battle(player['id'], store.begin_battle(player['id']), 0)
            self.assertEqual((second['old_trophies'], second['old_highest_trophies'], second['old_experience']), (8, 8, 8))
            abandoned = store.begin_battle(player['id'])
            store.abandon_battle(player['id'], abandoned)
            self.assertIsNone(store.complete_battle(player['id'], abandoned, 0))
            self.assertEqual(store.login(player['id'], player['token'])['tokens'], 40)

    def test_variable_integers(self):
        for value in (-(2**31), -8193, -65, -64, -1, 0, 1, 63, 64, 8191, 8192, 2**31-1):
            self.assertEqual(Reader(Writer().vint(value).bytes()).vint(), value)
        with self.assertRaises(ValueError):
            Reader(b'\x80' * 5).vint()

    def test_login_fields(self):
        w = Writer().integer(0).integer(42).string('secret').integer(25).integer(0).integer(107).string('hash')
        self.assertEqual(decode_login(w.bytes()), ((0, 42), 'secret', (25, 0, 107), 'hash'))
        with self.assertRaises(ValueError):
            decode_login(w.bytes()[:-1])

if __name__ == '__main__':
    unittest.main()
