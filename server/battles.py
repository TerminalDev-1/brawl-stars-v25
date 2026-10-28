"""v25 bot battle result handling."""
from protocol import Reader, Writer

def result_message(player, participants, outcome, reward, trophy_delta, old_trophies):
    """Encode the v25 battle-result structure consumed by the native client."""
    w = Writer()
    w.values(0, outcome, reward, trophy_delta, *([0] * 12))
    # Ten adjacent boolean fields are packed low-bit first.
    w.data.extend((16, 0))
    w.vint(len(participants))
    human_team = next(p['team'] for p in participants if p['local'])
    for p in participants:
        flags = int(p['local']) | (int(p['team'] != human_team) << 1)
        w.data.append(flags)
        w.reference(16, p['brawler'])
        if p['skin'] is None:
            w.vint(0)
        else:
            w.reference(29, p['skin'])
        w.values(old_trophies if p['local'] else 0, 0, 0)
        w.boolean(p['local'])
        if p['local']:
            w.integer(0).integer(player['id'])
        w.string(player['name'] if p['local'] else 'Bot ' + p['name'])
        w.values(1, 28000000, 43000000)
    w.values(1, 0, 8, 0, 0, 2, 1, old_trophies, old_trophies, 5, 1, 0)
    w.reference(28, 0).boolean(False)
    return w.bytes()


def read_result(payload):
    r = Reader(payload)
    outcome, mode, rank = r.vint(), r.vint(), r.vint()
    table, location, count = r.vint(), r.vint(), r.vint()
    if outcome not in (0, 1, 2) or mode != 1 or rank != 0 or (table, location, count) != (15, 7, 6):
        raise ValueError('unexpected bot battle result')
    participants = []
    for _ in range(count):
        if r.vint() != 16:
            raise ValueError('invalid battle character')
        character = r.vint()
        skin_table = r.vint()
        if skin_table not in (0, 29):
            raise ValueError('invalid battle skin')
        skin = r.vint() if skin_table else None
        team, local, name = r.vint(), r.vint(), r.string()
        if not 0 <= character < 32 or team not in (0, 1) or local not in (0, 1) or not name or len(name) > 40:
            raise ValueError('invalid battle participant')
        participants.append({'brawler': character, 'skin': skin, 'team': team, 'local': bool(local), 'name': name})
    if r.offset != len(payload) or sum(p['local'] for p in participants) != 1:
        raise ValueError('invalid battle roster')
    if any(sum(p['team'] == team for p in participants) != 3 for team in (0, 1)):
        raise ValueError('invalid team composition')
    if next(p for p in participants if p['local'])['brawler'] != 0:
        raise ValueError('unowned brawler')
    return outcome, participants
