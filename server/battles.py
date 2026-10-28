"""v25 bot battle result handling."""
from protocol import Reader, Writer

# Milestone types from csv_logic/milestones.csv used by the result screen.
MILESTONE_BRAWLER_RANK = 1
MILESTONE_EXPERIENCE = 5
# Reward-pair type the client sums as battle experience (shown as "Victory").
REWARD_EXPERIENCE = 0
STARTER_POWER = 1


def result_message(player, participants, outcome, progress):
    """Encode the v25 battle-end message (23456) for the native client.

    Layout, as decoded by libg.so 25.107 at 0x141274:
    16 varints, 10 packed booleans, players, (type, amount) reward pairs,
    reward references, (milestone, value, highest) progress triples,
    a data reference and an optional trailing object.
    """
    w = Writer()
    # Header: [0] result layout (0 = 3v3), [1] outcome, [2] tokens, [3] trophy change.
    w.values(0, outcome, progress['reward'], progress['trophy_delta'], *([0] * 12))
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
        # Trophies, alternative score (unused here), power level as displayed.
        w.values(progress['old_trophies'] if p['local'] else 0, 0, STARTER_POWER)
        w.boolean(p['local'])
        if p['local']:
            w.integer(0).integer(player['id'])
        w.string(player['name'] if p['local'] else 'Bot ' + p['name'])
        w.values(1, 28000000, 43000000)
    w.vint(1).values(REWARD_EXPERIENCE, progress['experience_gain'])
    w.vint(0)
    # The client animates each bar from these starting values. Without them the
    # rank badge and bars are never initialised and loop their raw animation.
    w.vint(2)
    w.values(MILESTONE_BRAWLER_RANK, progress['old_trophies'], progress['old_highest_trophies'])
    w.values(MILESTONE_EXPERIENCE, progress['old_experience'], progress['old_experience'])
    w.vint(0)
    w.boolean(False)
    return w.bytes()


def read_result(payload):
    r = Reader(payload)
    # The second value comes from client game state and the third is only set
    # for Showdown placements; neither affects Gem Grab rewards.
    outcome, state, rank = r.vint(), r.vint(), r.vint()
    table, location, count = r.vint(), r.vint(), r.vint()
    if outcome not in (0, 1, 2) or (table, location, count) != (15, 7, 6):
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
        # characters.csv in 25.107 has 103 rows.
        if not 0 <= character < 103 or team not in (0, 1) or local not in (0, 1) or not name or len(name) > 40:
            raise ValueError('invalid battle participant')
        participants.append({'brawler': character, 'skin': skin, 'team': team, 'local': bool(local), 'name': name})
    if r.offset != len(payload) or sum(p['local'] for p in participants) != 1:
        raise ValueError('invalid battle roster')
    if any(sum(p['team'] == team for p in participants) != 3 for team in (0, 1)):
        raise ValueError('invalid team composition')
    if next(p for p in participants if p['local'])['brawler'] != 0:
        raise ValueError('unowned brawler')
    return outcome, participants
