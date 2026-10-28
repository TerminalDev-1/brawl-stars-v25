"""Provisional v25 login and starter home serialization.

Field order is informed by DDBS-V25; these layouts require client validation.
"""
from protocol import Writer
from battles import BIG_BOX_COST, BRAWL_BOX_COST, EVENT_LOCATIONS
from brawlers import SHELLY, STARTER_BRAWLERS, unlock_card

def login_ok(player):
    w = Writer()
    for n in (0, player['id'], 0, player['id']): w.integer(n)
    for s in (player['token'], None, None): w.string(s)
    for n in (25, 107, 0): w.integer(n)
    w.string('dev')
    for n in (1, 0, 0): w.integer(n)
    for _ in range(3): w.string()
    w.integer(0).string().string('GB').string().integer(1).string()
    w.integer(0).integer(0).vint(0).string().values(1, 1).string()
    return w.bytes()

def home_data(p, pending=()):
    """Own home data (24101). pending: (type, amount) gains the lobby animates."""
    w = Writer()
    w.values(0, 0, p.get('trophies', 0), max(p.get('highest_trophies', 0), p.get('trophies', 0)), 0, 95, 99999).reference(28, 0).reference(43, 0)
    w.values(0, 1).reference(29, 0).values(1).reference(29, 0)
    w.values(0, 0, 0).boolean(False).vint(1).boolean(True)
    w.values(0, 1209599, 0, 0, 0, 0, 8)
    w.boolean(True).boolean(True).boolean(True)
    # Ends with the selected brawler.
    w.values(0, 0, 0, 0, 200, 0, 0, 0, 0).reference(16, p.get('selected_brawler', SHELLY))
    w.string('GB').string('')
    # Pending gains (libg ClientHome daily data +0xc4), as int pairs.
    w.vint(len(pending))
    for kind, amount in pending:
        w.integer(kind).integer(amount)
    w.values(0, 0, 0, 0, 2019049, BRAWL_BOX_COST, 10, 30, 3, 80, 10, 50, 1000, 500, 50, 999900, 0)
    w.vint(20)
    for i in range(20): w.vint(i)
    # Event slots: slot, slot index, ?, seconds left, ?, location, ...
    w.vint(len(EVENT_LOCATIONS))
    for slot, location in enumerate(EVENT_LOCATIONS, 1):
        w.values(slot, slot, 0, 86400, 0).reference(15, location).vint(3).string().values(0, 0, 0).boolean(False).vint(0)
    w.vint(0)
    for vals in ((20,35,75,140,290,480,800,1250),(1,2,3,4,5,10,15,20),(10,30,80),(6,20,60),(20,50,140,280),(150,400,1200,2600)):
        w.vint(len(vals)).values(*vals)
    # Config +0xa8..: ?, daily token limit, tokens per refresh, refresh seconds, star box cost, ...
    w.values(0, 200, 20, 8640, BIG_BOX_COST, 5, 6, 50, 604800).boolean(True)
    w.values(0, 1).integer(1).integer(41000000).integer(0).integer(1)
    w.values(0, 0).boolean(False).values(0, 0, 0, p['id'], 0, 0, 0, 0)
    name = p.get('name', 'Guest')
    w.string(name).vint(0 if name == 'Guest' else 1).integer(0).vint(8)
    brawlers = p.get('brawlers') or {b: (0, 0, 0, 0) for b in STARTER_BRAWLERS}
    owned = sorted(brawlers)
    # Resources: one unlock card per owned brawler, then tokens (Gold),
    # coins (HeroLvlUpMaterial), star tokens (FirstWins) and LegendaryTrophies.
    w.vint(len(owned) + 4)
    for b in owned:
        w.reference(23, unlock_card(b)).vint(1)
    w.values(5, 1, p.get('tokens', 0), 5, 8, p.get('coins', 0), 5, 9, p.get('star_tokens', 0), 5, 10, 0)
    # Per-brawler lists: trophies, highest trophies, (empty), power points, power level.
    def per_brawler(column):
        w.vint(len(owned))
        for b in owned:
            w.reference(16, b).vint(brawlers[b][column])
    per_brawler(0)
    per_brawler(1)
    w.vint(0)
    per_brawler(2)
    per_brawler(3)
    w.values(0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 1585502369)
    return w.bytes()
