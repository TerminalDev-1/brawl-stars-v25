"""v25 bot battle modes, rewards and result handling."""
from dataclasses import dataclass
from protocol import Reader, Writer
from brawlers import OWNED_BRAWLERS

# Milestone types from csv_logic/milestones.csv used by the result screen.
MILESTONE_BRAWLER_RANK = 1
MILESTONE_EXPERIENCE = 5
# Reward-pair type the client sums as battle experience.
REWARD_EXPERIENCE = 0
EXPERIENCE_REWARD = 8
STARTER_POWER = 1
# Pending gain types the lobby animates into its counters (libg 0x23f2e4, 0x1cfb6c).
PENDING_TOKENS = 3
PENDING_TROPHIES = 4
PENDING_STAR_TOKENS = 5
# This server's reward boost on the game's usual amounts.
TOKEN_MULTIPLIER = 80
STAR_TOKEN_MULTIPLIER = 8
# Tokens and star tokens needed for a box (the game's defaults are 100 and 10).
BRAWL_BOX_COST = 1
BIG_BOX_COST = 1


@dataclass(frozen=True)
class Mode:
    name: str
    location: int          # row in csv_logic/locations.csv
    players: int
    team_size: int
    layout: int            # battle-end screen layout (header value 0)
    tokens: tuple          # indexed by outcome (Gem Grab) or placement - 1
    trophies: tuple
    star_tokens: tuple     # one star token for a win, before the multiplier

    @property
    def placement(self):
        return self.team_size == 1


# Gem Grab outcome order is win, loss, draw. Showdown values are for the
# 0-49 trophy bracket, the only one a new account can reach so far. The
# Showdown token amounts, and counting places 1-4 as a Showdown win for star
# tokens, are this server's choice, not taken from the client.
GEM_GRAB = Mode('Gem Grab', 7, 6, 3, 0, (20, 10, 15), (8, 0, 0), (1, 0, 0))
SOLO_SHOWDOWN = Mode('Solo Showdown', 220, 10, 1, 2,
                     (20, 18, 16, 14, 12, 10, 8, 6, 4, 2),
                     (10, 8, 7, 6, 4, 2, 2, 1, 0, 0),
                     (1, 1, 1, 1, 0, 0, 0, 0, 0, 0))
MODES = {m.location: m for m in (GEM_GRAB, SOLO_SHOWDOWN)}
# Event slots offered in the lobby. The client also shows a Duo button for
# Showdown, but it falls back to Gem Grab; Duo is not supported yet.
EVENT_LOCATIONS = (GEM_GRAB.location, SOLO_SHOWDOWN.location)


@dataclass
class BattleResult:
    mode: Mode
    outcome: int           # Gem Grab: 0 win, 1 loss, 2 draw
    placement: int         # Showdown: 1 is first place
    participants: list

    @property
    def standing(self):
        """Index into the mode's reward tables."""
        return self.placement - 1 if self.mode.placement else self.outcome

    @property
    def reward(self):
        return self.mode.tokens[self.standing] * TOKEN_MULTIPLIER

    @property
    def star_token_reward(self):
        return self.mode.star_tokens[self.standing] * STAR_TOKEN_MULTIPLIER

    @property
    def trophy_delta(self):
        return self.mode.trophies[self.standing]

    @property
    def brawler(self):
        return next(p['brawler'] for p in self.participants if p['local'])

    @property
    def screen_outcome(self):
        """Header value 1: the outcome, or the placement in Showdown layouts."""
        return self.placement if self.mode.placement else self.outcome


def pending_gains(progress):
    """Counter animations the lobby plays after the next home data."""
    gains = []
    if progress['reward'] > 0:
        gains.append((PENDING_TOKENS, progress['reward']))
    if progress['trophy_delta'] > 0:
        gains.append((PENDING_TROPHIES, progress['trophy_delta']))
    if progress.get('star_token_gain', 0) > 0:
        gains.append((PENDING_STAR_TOKENS, progress['star_token_gain']))
    return gains


def result_message(player, result, progress):
    """Encode the v25 battle-end message (23456) for the native client.

    Layout, as decoded by libg.so 25.107 at 0x141274:
    16 varints, 10 packed booleans, players, (type, amount) reward pairs,
    reward references, (milestone, value, highest) progress triples,
    a data reference and an optional trailing object.
    """
    w = Writer()
    # Header: [0] screen layout, [1] outcome or placement, [2] tokens, [3] trophy change.
    w.values(result.mode.layout, result.screen_outcome, progress['reward'], progress['trophy_delta'], *([0] * 12))
    # Ten adjacent boolean fields are packed low-bit first.
    w.data.extend((16, 0))
    participants = result.participants
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
    """Decode a 14110 bot-battle result sent by the client's local simulation."""
    r = Reader(payload)
    # The second value comes from client game state. The third is the
    # Showdown placement (libg 0x47db24): teams still standing, plus one.
    outcome, _state, placement = r.vint(), r.vint(), r.vint()
    table, location, count = r.vint(), r.vint(), r.vint()
    mode = MODES.get(location)
    if table != 15 or mode is None or count != mode.players or outcome not in (0, 1, 2):
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
        # characters.csv in 25.107 has 103 rows; Terra appends Pixel as row 103.
        if not 0 <= character <= 103 or not 0 <= team < count or local not in (0, 1) or not name or len(name) > 40:
            raise ValueError('invalid battle participant')
        participants.append({'brawler': character, 'skin': skin, 'team': team, 'local': bool(local), 'name': name})
    if r.offset != len(payload) or sum(p['local'] for p in participants) != 1:
        raise ValueError('invalid battle roster')
    teams = count // mode.team_size
    if sorted({p['team'] for p in participants}) != list(range(teams)) or \
            any(sum(p['team'] == t for p in participants) != mode.team_size for t in range(teams)):
        raise ValueError('invalid team composition')
    if next(p for p in participants if p['local'])['brawler'] not in OWNED_BRAWLERS:
        raise ValueError('unowned brawler')
    if mode.placement and not 1 <= placement <= teams:
        raise ValueError('invalid placement')
    return BattleResult(mode, outcome, placement, participants)
