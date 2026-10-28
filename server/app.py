"""Experimental v25 listener; login and home layouts await client validation."""
import argparse
import asyncio
import logging
from protocol import Reader, Writer, packet, read_packet
from messages import login_ok, home_data
from battles import EXPERIENCE_REWARD, pending_gains, read_result, result_message
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
    active_match = None
    pending = []
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
            elif kind == 14103 and player is not None:
                if not body:
                    if active_match is not None:
                        accounts.abandon_battle(player['id'], active_match)
                    active_match = accounts.begin_battle(player['id'])
                    log.info('local bot battle started for account %d', player['id'])
                else:
                    request = Reader(body)
                    fields = [request.vint() for _ in range(4)]
                    log.info('battle request fields %s', fields)
                    writer.write(packet(20405, Writer().integer(0).integer(1).integer(6).integer(0).boolean(False).bytes()))
                    await writer.drain()
            elif kind == 14110 and player is not None:
                if active_match is None:
                    log.warning('battle result ignored: no active match')
                    continue
                try:
                    result = read_result(body)
                except ValueError:
                    log.warning('rejected battle result payload %s', body.hex())
                    raise
                progress = accounts.complete_battle(player['id'], active_match, result.reward, result.trophy_delta, EXPERIENCE_REWARD)
                if progress is None:
                    log.warning('battle result already processed')
                    active_match = None
                    continue
                active_match = None
                player['tokens'], player['trophies'] = progress['tokens'], progress['trophies']
                pending = pending_gains(progress)
                writer.write(packet(23456, result_message(player, result, progress)))
                await writer.drain()
                log.info('%s complete account=%d outcome=%d placement=%d reward=%d trophies=%+d tokens=%d',
                         result.mode.name, player['id'], result.outcome, result.placement,
                         progress['reward'], progress['trophy_delta'], progress['tokens'])
            elif kind in (14109, 14101) and player is not None:
                if active_match is not None:
                    accounts.abandon_battle(player['id'], active_match)
                    active_match = None
                writer.write(packet(24101, home_data(player, pending)))
                pending = []
                await writer.drain()
            elif kind == 10108:
                writer.write(packet(20108))
                await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    except (ValueError, UnicodeError) as exc:
        log.warning('invalid message from %s: %s', peer, exc)
    finally:
        if player is not None and active_match is not None:
            accounts.abandon_battle(player['id'], active_match)
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
