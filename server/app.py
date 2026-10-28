"""Experimental v25 listener; login and home layouts await client validation."""
import argparse
import asyncio
import logging
from protocol import Reader, Writer, packet, read_packet
from messages import login_ok, home_data
from storage import Accounts
from pathlib import Path

log = logging.getLogger('terra')
accounts = Accounts(Path(__file__).parent / 'data' / 'accounts.sqlite3')

def decode_login(payload):
    r = Reader(payload)
    account = (r.integer(), r.integer())
    token = r.string()
    major, minor, build = r.integer(), r.integer(), r.integer()
    fingerprint = r.string()
    return account, token, (major, minor, build), fingerprint

async def client(reader, writer):
    peer = writer.get_extra_info('peername')
    log.info('connected %s', peer)
    player = None
    try:
        while True:
            kind, version, body = await read_packet(reader)
            log.info('message %d version %d bytes %d', kind, version, len(body))
            if kind == 10101:
                account, token, client_version, fingerprint = decode_login(body)
                log.info('login account %s client version %s', account, client_version)
                if account[0] != 0 or client_version[0] != 25:
                    log.warning('unsupported account or client version'); break
                player = accounts.login(account[1], token)
                if player is None:
                    log.warning('account authentication failed'); break
                writer.write(packet(20104, login_ok(player), 1) + packet(24101, home_data(player)))
                await writer.drain()
            elif kind == 10212 and player is not None:
                r = Reader(body)
                name, state = r.string(), r.vint()
                if name and 2 <= len(name) <= 20:
                    accounts.set_name(player['id'], name)
                    player['name'] = name
                    response = Writer().vint(201).string(name).vint(state).bytes()
                    writer.write(packet(24111, response))
                else:
                    writer.write(packet(20205, Writer().vint(0).bytes()))
                await writer.drain()
            elif kind == 14600 and player is not None:
                name = Reader(body).string()
                writer.write(packet(20300, Writer().vint(0).integer(0).string(name).bytes()))
                await writer.drain()
            elif kind == 10108:
                writer.write(packet(20108))
                await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    except (ValueError, UnicodeError) as exc:
        log.warning('invalid message from %s: %s', peer, exc)
    finally:
        writer.close()
        await writer.wait_closed()
        log.info('disconnected %s', peer)

async def main(host, port):
    server = await asyncio.start_server(client, host, port)
    log.info('listening on %s', server.sockets[0].getsockname())
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9339)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
