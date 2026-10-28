"""Brawl Box and Big Box contents and the delivery command that shows them.

Box contents are this server's own design; the client only animates what the
server sends. Wire formats were read from libg.so 25.107: the client's open
box command is 500 (field: box type) and the server answers with command 203
(delivery units of drops, decoded at 0x128a14, drops at 0x4ae53c).
"""
from protocol import Writer
from brawlers import BRAWLERS

# Box types in the client's open box command (500).
BRAWL_BOX = 5      # the token box; on this server it opens a Mega Box
BIG_BOX = 4        # paid with star tokens
# Delivery unit types: the box the opening animation shows (libg 0x5fccf8:
# 10 Brawl Box, 11 Mega Box, 12 Big Box).
MEGA_BOX_UNIT = 11
UNIT_TYPE = {BRAWL_BOX: MEGA_BOX_UNIT, BIG_BOX: 12}
# How many Brawl Boxes' worth of contents each box holds.
BOX_ROLLS = {BRAWL_BOX: 10, BIG_BOX: 3}

# Drop types handled by the client (libg 0x36d4a8).
DROP_BRAWLER = 1
DROP_POWER_POINTS = 6
DROP_COINS = 7

BRAWLER_CHANCE = 0.10
RARITY_WEIGHT = {'common': 10, 'rare': 8, 'super_rare': 6, 'epic': 4, 'mega_epic': 2, 'legendary': 1}


def roll(rng, box_type, owned):
    """Return drops as (drop type, amount, brawler or None)."""
    owned = set(owned)
    coins = power_points = 0
    unlocked = []
    for _ in range(BOX_ROLLS[box_type]):
        coins += rng.randint(8, 38)
        power_points += rng.randint(4, 20)
        locked = [b for b in BRAWLERS if b not in owned and b not in unlocked]
        if locked and rng.random() < BRAWLER_CHANCE:
            weights = [RARITY_WEIGHT[BRAWLERS[b][2]] for b in locked]
            unlocked.append(rng.choices(locked, weights)[0])
    drops = [(DROP_COINS, coins, None)]
    targets = sorted(owned)
    # Split power points over up to two owned brawlers.
    picks = rng.sample(targets, min(2, len(targets)))
    for i, brawler in enumerate(picks):
        share = power_points // len(picks) + (power_points % len(picks) if i == 0 else 0)
        drops.append((DROP_POWER_POINTS, share, brawler))
    drops += [(DROP_BRAWLER, 1, b) for b in unlocked]
    return drops


def delivery_command(box_type, drops, tick):
    """AvailableServerCommand (24111) body carrying command 203."""
    w = Writer().vint(203)
    w.vint(0)                       # stored by the client as daily data +0xb0
    w.vint(1).vint(UNIT_TYPE[box_type]).vint(len(drops))
    for drop_type, amount, brawler in drops:
        w.vint(amount)
        if brawler is None:
            w.vint(0)
        else:
            w.reference(16, brawler)
        w.vint(drop_type).vint(0).vint(0).vint(0)
    # No trailing object; the three values after it are unused when zero.
    w.boolean(False).values(0, 0, 0)
    # Server command base, then the command base: ticks and an empty id.
    w.vint(0).values(tick, tick, 0, 0)
    return w.bytes()

