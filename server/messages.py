"""Provisional v25 login and starter home serialization.

Field order is informed by DDBS-V25; these layouts require client validation.
"""
from protocol import Writer

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

def home_data(p):
    w = Writer()
    w.values(0, 0, p.get('trophies', 0), p.get('trophies', 0), 0, 95, 99999).reference(28, 0).reference(43, 0)
    w.values(0, 1).reference(29, 0).values(1).reference(29, 0)
    w.values(0, 0, 0).boolean(False).vint(1).boolean(True)
    w.values(0, 1209599, 0, 0, 0, 0, 8)
    w.boolean(True).boolean(True).boolean(True)
    w.values(0, 0, 0, 0, 200, 0, 0, 0, 0).reference(16, 0)
    w.string('GB').string('')
    w.values(0, 0, 0, 0, 0, 2019049, 100, 10, 30, 3, 80, 10, 50, 1000, 500, 50, 999900, 0)
    w.vint(20)
    for i in range(20): w.vint(i)
    w.vint(1).values(1, 1, 0, 86400, 0).reference(15, 7).vint(3).string().values(0, 0, 0).boolean(False).vint(0)
    w.vint(0)
    for vals in ((20,35,75,140,290,480,800,1250),(1,2,3,4,5,10,15,20),(10,30,80),(6,20,60),(20,50,140,280),(150,400,1200,2600)):
        w.vint(len(vals)).values(*vals)
    w.values(0, 200, 20, 8640, 10, 5, 6, 50, 604800).boolean(True)
    w.values(0, 1).integer(1).integer(41000000).integer(0).integer(1)
    w.values(0, 0).boolean(False).values(0, 0, 0, p['id'], 0, 0, 0, 0)
    name = p.get('name', 'Guest')
    w.string(name).vint(0 if name == 'Guest' else 1).integer(0).vint(8)
    # Starter Shelly unlock card and resource counters.
    w.vint(5).values(23, 0, 1, 5, 1, p.get('tokens', 0), 5, 8, 0, 5, 9, 0, 5, 10, 0)
    for _ in range(2): w.vint(1).reference(16, 0).vint(p.get('trophies', 0))
    w.vint(0)
    w.vint(1).reference(16, 0).vint(0)
    w.vint(1).reference(16, 0).vint(0)
    w.values(0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 1585502369)
    return w.bytes()
