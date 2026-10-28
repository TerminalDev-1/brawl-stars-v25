import asyncio
from contextlib import closing
import sqlite3
import unittest
import tempfile
from pathlib import Path
from storage import Accounts
from battles import GEM_GRAB, SOLO_SHOWDOWN, pending_gains, read_result, result_message
from messages import home_data
import random
from boxes import BIG_BOX, BRAWL_BOX, DROP_BRAWLER, DROP_COINS, DROP_POWER_POINTS, box_requests, delivery_command, roll
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
                        self.assertEqual(db.execute('SELECT tokens, star_tokens FROM accounts WHERE id=?', (account_id,)).fetchone(), (20, 8))
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
        result = read_result(payload)
        roster = result.participants
        self.assertEqual((result.mode, result.outcome, result.reward, result.trophy_delta, result.star_token_reward), (GEM_GRAB, 0, 20, 8, 8))
        self.assertEqual(len(roster), 6)
        self.assertEqual(sum(p['local'] for p in roster), 1)
        progress = {'reward': 20, 'trophy_delta': 8, 'old_trophies': 8, 'old_highest_trophies': 8,
                    'old_experience': 16, 'experience_gain': 8}
        encoded = result_message({'id': 1, 'name': 'Test'}, result, progress)
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
        self.assertEqual(read_result(bytes.fromhex('0002') + payload[2:]).outcome, 0)

    def test_solo_showdown_result(self):
        # Native v25 Solo Showdown win on location 220: ten players, one per team.
        payload = bytes.fromhex('0100010f9c030a10001d00000100000003646576100c0001000000000131101e000200000000013210020003000000000133101e0004000000000134100e0005000000000135100f0006000000000136100e00070000000001371010000800000000013810100009000000000139')
        result = read_result(payload)
        self.assertEqual((result.mode, result.placement, result.reward, result.trophy_delta, result.star_token_reward), (SOLO_SHOWDOWN, 1, 20, 10, 8))
        self.assertEqual(len(result.participants), 10)
        progress = {'reward': 20, 'trophy_delta': 10, 'old_trophies': 24, 'old_highest_trophies': 24,
                    'old_experience': 0, 'experience_gain': 8}
        r = Reader(result_message({'id': 1, 'name': 'Test'}, result, progress))
        # Showdown layout with the placement in place of the outcome.
        self.assertEqual([r.vint() for _ in range(4)], [2, 1, 20, 10])
        # Tenth place earns nothing and an impossible placement is rejected.
        last = bytearray(payload); last[2] = 10
        self.assertEqual((read_result(bytes(last)).reward, read_result(bytes(last)).star_token_reward), (2, 0))
        self.assertEqual(read_result(bytes(last)).trophy_delta, 0)
        last[2] = 11
        with self.assertRaises(ValueError):
            read_result(bytes(last))
        # A Gem Grab location with a Showdown roster is rejected.
        wrong = payload[:4] + bytes([7]) + payload[6:]
        with self.assertRaises(ValueError):
            read_result(wrong)

    def test_lobby_animates_pending_gains(self):
        progress = {'reward': 20, 'trophy_delta': 8}
        self.assertEqual(pending_gains(progress), [(3, 20), (4, 8)])
        self.assertEqual(pending_gains({'reward': 10, 'trophy_delta': 0}), [(3, 10)])
        self.assertEqual(pending_gains({'reward': 160, 'trophy_delta': 8, 'star_token_gain': 8}), [(3, 160), (4, 8), (5, 8)])
        player = {'id': 1, 'name': 'Test', 'tokens': 30, 'trophies': 8}
        plain, animated = home_data(player), home_data(player, [(3, 20), (4, 8)])
        # Two int pairs replace the empty list count.
        self.assertEqual(len(animated) - len(plain), 16)
        marker = Writer().string('GB').string('').bytes()
        at = plain.index(marker) + len(marker)
        self.assertEqual(plain[at], 0)
        r = Reader(animated[at:])
        self.assertEqual([r.vint(), r.integer(), r.integer(), r.integer(), r.integer()], [2, 3, 20, 4, 8])

    def test_box_opening(self):
        # Native v25 EndClientTurn with one open box command (500) for a Brawl Box.
        self.assertEqual(box_requests(bytes.fromhex('00b9050001b407b805b8057f7f05ffffffff')), [(BRAWL_BOX, 376)])
        drops = roll(random.Random(1), BIG_BOX, [0, 103])
        self.assertEqual(drops[0][0], DROP_COINS)
        self.assertTrue(24 <= drops[0][1] <= 114)
        self.assertTrue(all(b in (0, 103) for t, _, b in drops if t == DROP_POWER_POINTS))
        with tempfile.TemporaryDirectory() as tmp:
            store = Accounts(Path(tmp) / 'accounts.sqlite3')
            player = store.login(0, None)
            self.assertIsNone(store.open_box(player['id'], 'tokens', 1, lambda owned: []))
            store.complete_battle(player['id'], store.begin_battle(player['id']), 0, 2, 0, 0)
            fixed = [(DROP_COINS, 30, None), (DROP_POWER_POINTS, 12, 103), (DROP_BRAWLER, 1, 5)]
            drops, state = store.open_box(player['id'], 'tokens', 1, lambda owned: fixed)
            self.assertEqual((drops, state['tokens'], state['coins']), (fixed, 1, 30))
            self.assertEqual((state['brawlers'][103][2], 5 in state['brawlers']), (12, True))
            # The unlocked brawler can now be played and is listed in the home data.
            store.complete_battle(player['id'], store.begin_battle(player['id']), 5, 0, 8, 0)
            self.assertIn(Writer().reference(23, 20).vint(1).bytes(), home_data(store.login(player['id'], player['token'])))
        body = delivery_command(BRAWL_BOX, fixed, 376)
        r = Reader(body)
        # Command 203, one Mega Box unit (type 11) with three drops.
        self.assertEqual([r.vint() for _ in range(5)], [203, 0, 1, 11, 3])

    def test_battle_rewards_are_persistent_and_once_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Accounts(Path(tmp) / 'accounts.sqlite3')
            player = store.login(0, None)
            match = store.begin_battle(player['id'])
            self.assertEqual(store.complete_battle(player['id'], match, 0, 20, 8, 8)['tokens'], 20)
            self.assertIsNone(store.complete_battle(player['id'], match, 0, 20, 8, 8))
            restored = store.login(player['id'], player['token'])
            self.assertEqual((restored['tokens'], restored['trophies']), (20, 8))
            second = store.complete_battle(player['id'], store.begin_battle(player['id']), 0, 20, 8, 8)
            self.assertEqual((second['old_trophies'], second['old_highest_trophies'], second['old_experience']), (8, 8, 8))
            abandoned = store.begin_battle(player['id'])
            store.abandon_battle(player['id'], abandoned)
            self.assertIsNone(store.complete_battle(player['id'], abandoned, 0, 20, 8, 8))
            self.assertEqual(store.login(player['id'], player['token'])['tokens'], 40)
            # Pixel keeps her own trophies; the account total is the sum.
            pixel = store.complete_battle(player['id'], store.begin_battle(player['id']), 103, 0, 10, 8)
            self.assertEqual((pixel['old_trophies'], pixel['trophies']), (0, 26))
            restored = store.login(player['id'], player['token'])
            self.assertEqual((restored['brawlers'], restored['selected_brawler']), ({0: (16, 16, 0, 0), 103: (10, 10, 0, 0)}, 103))
            with self.assertRaises(ValueError):
                store.complete_battle(player['id'], store.begin_battle(player['id']), 1, 0, 8, 8)
            # Pixel's unlock card (23, 224) is listed after Shelly's (23, 0).
            home = home_data(restored)
            self.assertIn(Writer().values(2 + 4, 23, 0, 1, 23, 224, 1).bytes(), home)

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
