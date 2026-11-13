# -*- coding: utf-8 -*-
"""Logika editor file .bin / .str (tanpa tampilan, mudah diuji)."""
import os, re, shutil, struct

MANIFEST = '_cpk_manifest.json'
BACKUP_DIR = '_cpk_backup'


class EditError(Exception):
    pass


# ---------------------------------------------------------------- teks
_U8 = (rb'(?:[\x20-\x7e]'
       rb'|[\xc2-\xdf][\x80-\xbf]'
       rb'|[\xe0-\xef][\x80-\xbf]{2}'
       rb'|[\xf0-\xf4][\x80-\xbf]{3}){4,}')
_STR = re.compile(_U8)


def find_strings(data):
    """Daftar teks di dalam data: [(offset, panjang_byte, teks)]"""
    out = []
    for m in _STR.finditer(bytes(data)):
        raw = m.group()
        try:
            t = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if sum(1 for c in t if c.isalpha()) < 3:   # buang sampah biner
            continue
        out.append((m.start(), len(raw), t))
    return out


def replace_text(data, off, maxlen, text):
    """Timpa teks di off. Boleh lebih pendek (sisa diisi 00), tidak boleh lebih panjang."""
    nb = text.encode('utf-8')
    if len(nb) > maxlen:
        raise EditError('Teks terlalu panjang: %d byte, maksimal %d byte.' % (len(nb), maxlen))
    data[off:off + maxlen] = nb + b'\x00' * (maxlen - len(nb))


# ---------------------------------------------------------------- angka
KINDS = {'1 byte (0-255)': ('B', 1), '2 byte (0-65535)': ('<H', 2),
         '4 byte (0-4 miliar)': ('<I', 4)}


def parse_offset(s, size):
    s = (s or '').strip().replace(' ', '')
    if not s:
        raise EditError('Isi dulu offset-nya.')
    try:
        v = int(s, 0)
    except ValueError:
        try:
            v = int(s, 16) if any(c in 'abcdefABCDEF' for c in s) else int(s)
        except ValueError:
            raise EditError('Offset tidak dimengerti: %s' % s)
    if v < 0 or v >= size:
        raise EditError('Offset di luar file (ukuran file %d byte).' % size)
    return v


def read_number(data, off, kind):
    fmt, n = KINDS[kind]
    if off + n > len(data):
        raise EditError('Offset terlalu dekat ke ujung file.')
    return struct.unpack_from(fmt, data, off)[0]


def write_number(data, off, kind, value_text):
    fmt, n = KINDS[kind]
    try:
        v = int(str(value_text).strip(), 0)
    except ValueError:
        raise EditError('Nilai harus berupa angka.')
    if v < 0 or v >= 1 << (8 * n):
        raise EditError('Nilai di luar jangkauan untuk %s.' % kind)
    if off + n > len(data):
        raise EditError('Offset terlalu dekat ke ujung file.')
    struct.pack_into(fmt, data, off, v)


# ---------------------------------------------------------------- hex
def parse_hex(s):
    t = re.sub(r'(0x|[\s,;:-])', '', (s or ''), flags=re.I)
    if not t:
        raise EditError('Isi dulu byte hex-nya, contoh: 64 00')
    if len(t) % 2 or not re.fullmatch(r'[0-9a-fA-F]+', t):
        raise EditError('Hex tidak valid. Pakai pasangan 0-9 / A-F, contoh: 64 00')
    return bytes.fromhex(t)


def write_hex(data, off, hexstr):
    b = parse_hex(hexstr)
    if off + len(b) > len(data):
        raise EditError('Melewati ujung file. Ukuran file tidak boleh berubah.')
    data[off:off + len(b)] = b
    return len(b)


def hex_dump(data, off, rows=16, w=8):
    off -= off % w
    lines = []
    for r in range(rows):
        a = off + r * w
        if a >= len(data):
            break
        chunk = data[a:a + w]
        hx = ' '.join('%02X' % c for c in chunk).ljust(w * 3 - 1)
        tx = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        lines.append('%06X  %s  %s' % (a, hx, tx))
    return '\n'.join(lines)


# ---------------------------------------------------------------- cadangan
def find_root(path):
    d = os.path.dirname(os.path.abspath(path))
    cur = d
    while True:
        if os.path.isfile(os.path.join(cur, MANIFEST)):
            return cur
        up = os.path.dirname(cur)
        if up == cur:
            return d
        cur = up


def backup_path(path):
    root = find_root(path)
    return os.path.join(root, BACKUP_DIR, os.path.relpath(os.path.abspath(path), root))


def ensure_backup(path):
    bp = backup_path(path)
    if not os.path.exists(bp):
        os.makedirs(os.path.dirname(bp), exist_ok=True)
        shutil.copyfile(path, bp)


def has_backup(path):
    return os.path.exists(backup_path(path))


def restore_backup(path):
    bp = backup_path(path)
    if not os.path.exists(bp):
        return False
    shutil.copyfile(bp, path)
    return True


def load(path, limit=40 << 20):
    if os.path.getsize(path) > limit:
        raise EditError('File terlalu besar untuk diedit di HP (maks 40 MB).')
    with open(path, 'rb') as f:
        return bytearray(f.read())


def save(path, data):
    ensure_backup(path)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(bytes(data))
    os.replace(tmp, path)
