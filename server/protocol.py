"""Brawl Stars v25 packet framing and binary primitives."""
import asyncio
import struct

MAX_PAYLOAD = 2 * 1024 * 1024

async def read_packet(reader):
    header = await reader.readexactly(7)
    kind = int.from_bytes(header[:2], 'big')
    size = int.from_bytes(header[2:5], 'big')
    version = int.from_bytes(header[5:], 'big')
    if size > MAX_PAYLOAD:
        raise ValueError('packet exceeds size limit')
    return kind, version, await reader.readexactly(size)

def packet(kind, payload=b'', version=0):
    if not 0 <= kind <= 65535 or not 0 <= version <= 65535 or len(payload) > MAX_PAYLOAD:
        raise ValueError('invalid packet')
    return kind.to_bytes(2, 'big') + len(payload).to_bytes(3, 'big') + version.to_bytes(2, 'big') + payload

class Reader:
    def __init__(self, data):
        self.data = memoryview(data)
        self.offset = 0
    def take(self, n):
        if n < 0 or self.offset + n > len(self.data):
            raise ValueError('truncated packet')
        value = bytes(self.data[self.offset:self.offset+n])
        self.offset += n
        return value
    def integer(self):
        return struct.unpack('>i', self.take(4))[0]
    def vint(self):
        value = 0
        shift = 0
        negative = False
        for index in range(5):
            byte = self.take(1)[0]
            if index == 0:
                negative = bool(byte & 64)
                value = byte & 63
                shift = 6
            else:
                value |= (byte & 127) << shift
                shift += 7
            if not byte & 128:
                value = value - (1 << shift) if negative else value
                if not -(2**31) <= value < 2**31:
                    raise ValueError('variable integer out of range')
                return value
        raise ValueError('invalid variable integer')
    def string(self):
        n = self.integer()
        if n == -1:
            return None
        if not 0 <= n <= 65536:
            raise ValueError('invalid string')
        return self.take(n).decode('utf-8')

class Writer:
    def __init__(self):
        self.data = bytearray()
    def integer(self, n):
        self.data.extend(struct.pack('>i', n)); return self
    def string(self, value=None):
        if value is None:
            return self.integer(-1)
        b = value.encode('utf-8')
        self.integer(len(b)); self.data.extend(b); return self
    def vint(self, value):
        negative = value < 0
        byte = (value & 63) | (64 if negative else 0)
        value >>= 6
        while True:
            done = value == (-1 if negative else 0)
            self.data.append(byte | (0 if done else 128))
            if done:
                return self
            byte = value & 127
            value >>= 7
    def values(self, *values):
        for value in values:
            self.vint(value)
        return self
    def boolean(self, value):
        self.data.append(1 if value else 0); return self
    def reference(self, table, row):
        return self.values(table, row)
    def bytes(self):
        return bytes(self.data)
