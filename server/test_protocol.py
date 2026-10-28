import asyncio
import unittest
import tempfile
from pathlib import Path
from storage import Accounts
from unittest.mock import patch
from protocol import Reader, Writer, packet, read_packet
from app import decode_login, client

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
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
