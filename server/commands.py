"""Client commands carried in EndClientTurn (14102).

The message is three varints, a command count, then each command: its id,
a tick, a second tick and two empty ids (each -1), then its own fields.
Layouts were read from captures of the v25 client:

    500 open box:        box type (varint)
    520 upgrade brawler: brawler data reference (16, row)
    522 view upgrade:    brawler data reference, then unknown fields

Reading stops at a command whose layout is not known, so a later command in
the same message would be missed; the client sends one command per tap.
"""
import logging
from protocol import Reader

log = logging.getLogger('terra')

OPEN_BOX = 500
UPGRADE_BRAWLER = 520
VIEW_UPGRADE = 522


def _reference(r):
    table = r.vint()
    return (table, r.vint()) if table else None


def client_commands(body):
    """Yield (command id, tick, fields) for each decodable command."""
    r = Reader(body)
    for _ in range(3):
        r.vint()
    for _ in range(r.vint()):
        command = r.vint()
        tick = r.vint()
        r.vint(); r.vint(); r.vint()
        if command == OPEN_BOX:
            yield command, tick, (r.vint(),)
        elif command == UPGRADE_BRAWLER:
            yield command, tick, (_reference(r),)
        else:
            if command != VIEW_UPGRADE:
                log.info('unhandled client command %d in %s', command, body.hex())
            return
