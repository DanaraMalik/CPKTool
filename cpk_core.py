# -*- coding: utf-8 -*-
"""
Inti (core) pembongkar & penyusun arsip .cpk (CRI) + dekoder/enkoder WESYS
untuk data eFootball mobile.  Hanya memakai pustaka standar Python.

Alur:
  extract(cpk, folder)           -> bongkar semua file + tulis _cpk_manifest.json
  build(folder, cpk_baru, asli)  -> susun ulang jadi .cpk dari folder hasil bongkar
"""
import os, io, sys, json, struct, zlib, hashlib, base64, sys
from array import array

MANIFEST = '_cpk_manifest.json'
M32 = 0xffffffff
SEEDS = {1: (0x2e2aa6f2, 0x0cc8dcd3, 0x168ea000),   # (y, z, x)
         2: (0x4a523b4e, 0xf3a31bad, 0xed5b2960)}


class CpkError(Exception):
    pass


# ---------------------------------------------------------------- @UTF table
def _xor_utf(b):
    m, t = 0x655f, 0x4115
    out = bytearray(len(b))
    for i, d in enumerate(b):
        out[i] = d ^ (m & 0xff)
        m = (m * t) & M32
    return bytes(out)

_FMT = {0: ('>B', 1), 1: ('>b', 1), 2: ('>H', 2), 3: ('>h', 2), 4: ('>I', 4),
        5: ('>i', 4), 6: ('>Q', 8), 7: ('>q', 8), 8: ('>f', 4), 9: ('>d', 8)}


class UTF:
    """Tabel @UTF: self.cols = [(nama, storage, tipe, konstanta)], self.rows = [dict]"""
    def __init__(self, data):
        self.encrypted = data[:4] != b'@UTF'
        if self.encrypted:
            data = _xor_utf(data)
        if data[:4] != b'@UTF':
            raise CpkError('Bagian dalam CPK tidak dikenali (bukan @UTF).')
        (_size, rows_off, str_off, data_off, name_off,
         ncol, row_w, nrow) = struct.unpack('>IIIIIHHI', data[4:32])
        self.d = data
        self.rows_off, self.str_off, self.data_off = rows_off + 8, str_off + 8, data_off + 8
        self.name = self._cstr(name_off)
        p = 32
        self.cols = []
        for _ in range(ncol):
            fl = data[p]; p += 1
            noff = struct.unpack('>I', data[p:p + 4])[0]; p += 4
            st, ty = fl >> 4, fl & 0xf
            const = None
            if st == 3:
                const, p = self._val(ty, p)
            self.cols.append((self._cstr(noff), st, ty, const))
        self.rows = []
        rp = self.rows_off
        for _ in range(nrow):
            q, row = rp, {}
            for name, st, ty, const in self.cols:
                if st == 5:
                    v, q = self._val(ty, q)
                elif st == 3:
                    v = const
                else:
                    v = None
                row[name] = v
            self.rows.append(row)
            rp += row_w

    def _cstr(self, off):
        a = self.str_off + off
        return self.d[a:self.d.index(b'\x00', a)].decode('utf-8', 'replace')

    def _val(self, ty, p):
        d = self.d
        if ty in _FMT:
            f, n = _FMT[ty]
            return struct.unpack(f, d[p:p + n])[0], p + n
        if ty == 0xA:
            return self._cstr(struct.unpack('>I', d[p:p + 4])[0]), p + 4
        if ty == 0xB:
            o, s = struct.unpack('>II', d[p:p + 8])
            a = self.data_off + o
            return bytes(d[a:a + s]), p + 8
        raise CpkError('Tipe kolom tidak didukung: %x' % ty)


def utf_build(name, cols, rows, encrypt):
    strings = bytearray(b'<NULL>\x00')
    sidx = {'<NULL>': 0}
    def S(s):
        if s not in sidx:
            sidx[s] = len(strings)
            strings.extend(s.encode('utf-8') + b'\x00')
        return sidx[s]
    data = bytearray()
    def enc(ty, v):
        if ty in _FMT:
            return struct.pack(_FMT[ty][0], v)
        if ty == 0xA:
            return struct.pack('>I', S(v))
        if ty == 0xB:
            off = len(data); data.extend(v)
            return struct.pack('>II', off, len(v))
        raise CpkError('Tipe kolom tidak didukung: %x' % ty)
    name_off = S(name)
    colb = bytearray()
    for cname, st, ty, const in cols:
        colb += bytes([(st << 4) | ty]) + struct.pack('>I', S(cname))
        if st == 3:
            colb += enc(ty, const)
    rowb = bytearray(); row_w = 0
    for i, row in enumerate(rows):
        start = len(rowb)
        for cname, st, ty, const in cols:
            if st == 5:
                rowb += enc(ty, row[cname])
        if i == 0:
            row_w = len(rowb)
    pre = 32 + len(colb) + len(rowb)
    while (pre + len(strings)) % 8:
        strings.append(0)
    while len(data) % 8:
        data.append(0)
    rows_off = 32 + len(colb)
    str_off = rows_off + len(rowb)
    data_off = str_off + len(strings)
    total = data_off + len(data)
    head = b'@UTF' + struct.pack('>IIIIIHHI', total - 8, rows_off - 8, str_off - 8,
                                  data_off - 8, name_off, len(cols), row_w, len(rows))
    out = bytes(head + colb + rowb + strings + data)
    return _xor_utf(out) if encrypt else out


# ---------------------------------------------------------------- CRILAYLA
def crilayla(data):
    if data[:8] != b'CRILAYLA':
        raise CpkError('bukan CRILAYLA')
    usize, hoff = struct.unpack('<II', data[8:16])
    res = bytearray(usize + 0x100)
    res[:0x100] = data[hoff + 0x10: hoff + 0x10 + 0x100]
    inp = hoff + 0x10 - 1
    out_end = 0x100 + usize - 1
    pool = 0; left = 0
    def bits(n):
        nonlocal inp, pool, left
        o = 0; got = 0
        while got < n:
            if left == 0:
                pool = data[inp]; inp -= 1; left = 8
            take = min(left, n - got)
            o = (o << take) | ((pool >> (left - take)) & ((1 << take) - 1))
            left -= take; got += take
        return o
    written = 0
    while written < usize:
        if bits(1):
            off = bits(13) + 3
            ln = 3
            cont = True
            for vl in (2, 3, 5, 8):
                lv = bits(vl); ln += lv
                if lv != (1 << vl) - 1:
                    cont = False; break
            if cont:
                while True:
                    lv = bits(8); ln += lv
                    if lv != 255: break
            for _ in range(ln):
                res[out_end - written] = res[out_end - written + off]
                written += 1
        else:
            res[out_end - written] = bits(8)
            written += 1
    return bytes(res)


# ---------------------------------------------------------------- WESYS
def _keystream_xor(data, csz, usz, typ):
    """XOR (simetris: dipakai untuk enkripsi & dekripsi)."""
    y, z, x = SEEDS.get(typ, (0, 0, 0))
    w = (csz | (usz << 16)) & M32
    n = csz >> 2
    arr = array('I')
    arr.frombytes(bytes(data[:n * 4]))
    if sys.byteorder == 'big':
        arr.byteswap()
    for i in range(n):
        t = (x ^ (x << 11)) & M32
        nw = (w ^ (w >> 19) ^ t ^ (t >> 8)) & M32
        x, y, z, w = y, z, w, nw
        arr[i] ^= nw
    if sys.byteorder == 'big':
        arr.byteswap()
    return arr.tobytes() + bytes(data[n * 4:])


def is_wesys(buf):
    return len(buf) >= 16 and buf[0] == 0xff and buf[3:8] == b'WESYS'


def wesys_decode(buf):
    """-> (data, info). info dipakai lagi saat menyusun ulang."""
    if not is_wesys(buf):
        raise CpkError('bukan WESYS')
    flag = buf[2]; typ = buf[1] & 0xf
    csz, usz = struct.unpack('<II', buf[8:16])
    enc = (flag >> 1) & 1; comp = flag & 1
    data = bytes(buf[16:16 + csz])
    if enc:
        data = _keystream_xor(data, csz, usz, typ)
    zhdr = True
    if comp:
        try:
            data = zlib.decompress(data)
        except Exception:
            data = zlib.decompress(data, -15); zhdr = False
    info = {'b0': buf[0], 'b1': buf[1], 'flag': flag, 'zhdr': zhdr,
            'tail': max(0, len(buf) - 16 - csz)}
    return data, info


def wesys_encode(data, info):
    flag, typ = info['flag'], info['b1'] & 0xf
    if flag & 1:
        if info.get('zhdr', True):
            # kompres maksimal, tapi tetap berkepala zlib "78 01" seperti aslinya
            c = zlib.compressobj(9, zlib.DEFLATED, -15)
            body = (b'\x78\x01' + c.compress(data) + c.flush() +
                    struct.pack('>I', zlib.adler32(data) & M32))
        else:
            c = zlib.compressobj(1, zlib.DEFLATED, -15)
            body = c.compress(data) + c.flush()
    else:
        body = bytes(data)
    csz, usz = len(body), len(data)
    if flag & 2:
        body = _keystream_xor(body, csz, usz, typ)
    return (bytes([info['b0'], info['b1'], flag]) + b'WESYS' +
            struct.pack('<II', csz, usz) + body + b'\x00' * info.get('tail', 0))


# ---------------------------------------------------------------- CPK reader
class CPK:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        try:
            self._load()
        except CpkError:
            self.f.close(); raise
        except Exception as e:
            self.f.close()
            raise CpkError('File ini bukan CPK yang valid (%s).' % e)

    def _load(self):
        f = self.f
        head = f.read(16)
        if head[:4] != b'CPK ':
            raise CpkError('Ini bukan file CPK (kepala file tidak cocok).')
        self.magic_pad = head[4:8]
        usz = struct.unpack('<Q', head[8:16])[0]
        self.hdr = UTF(f.read(usz))
        self.hdr_len = usz
        h = self.hdr.rows[0]
        self.hrow = h
        toc, content = h['TocOffset'], h.get('ContentOffset')
        f.seek(toc)
        t = f.read(16)
        if t[:4] != b'TOC ':
            raise CpkError('Daftar isi (TOC) tidak ditemukan.')
        self.toc_pad = t[4:8]
        tsz = struct.unpack('<Q', t[8:16])[0]
        self.toc = UTF(f.read(tsz))
        self.toc_len = tsz
        base = toc if content is None else min(toc, content)
        self.base = base
        self.files = []
        for r in self.toc.rows:
            self.files.append({'dir': (r.get('DirName') or '').strip('/'),
                               'name': r['FileName'], 'size': r['FileSize'],
                               'esize': r.get('ExtractSize') or r['FileSize'],
                               'off': r['FileOffset'] + base, 'id': r.get('ID')})

    def read_raw(self, fi):
        self.f.seek(fi['off'])
        return self.f.read(fi['size'])

    def close(self):
        self.f.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def list_cpk(path):
    with CPK(path) as c:
        return [dict(x) for x in c.files]


# ---------------------------------------------------------------- helpers
def _b64(b): return base64.b64encode(bytes(b)).decode('ascii')
def _unb64(s): return base64.b64decode(s) if s else b''
def _md5(b): return hashlib.md5(b).hexdigest()

def _cols_to_json(cols):
    out = []
    for n, st, ty, const in cols:
        if isinstance(const, (bytes, bytearray)):
            const = {'hex': bytes(const).hex()}
        out.append([n, st, ty, const])
    return out

def _cols_from_json(cols):
    out = []
    for n, st, ty, const in cols:
        if isinstance(const, dict):
            const = bytes.fromhex(const['hex'])
        out.append((n, st, ty, const))
    return out

def _row_to_json(row):
    return {k: ({'hex': bytes(v).hex()} if isinstance(v, (bytes, bytearray)) else v)
            for k, v in row.items()}

def _row_from_json(row):
    return {k: (bytes.fromhex(v['hex']) if isinstance(v, dict) else v)
            for k, v in row.items()}

def _safe_join(root, *parts):
    p = os.path.normpath(os.path.join(root, *[x for x in parts if x]))
    r = os.path.abspath(root)
    if os.path.abspath(p) != r and not os.path.abspath(p).startswith(r + os.sep):
        raise CpkError('Nama file berbahaya di dalam CPK: %s' % '/'.join(parts))
    return p

def _md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()

def _prog(cb, i, n, msg):
    if cb:
        cb(i, n, msg)


# ---------------------------------------------------------------- EXTRACT
def extract(cpk_path, outdir, progress=None, decode=True):
    """Bongkar CPK. Return ringkasan (dict)."""
    with CPK(cpk_path) as c:
        os.makedirs(outdir, exist_ok=True)
        n = len(c.files)
        entries, n_dec, n_fail = [], 0, 0
        pad_pattern = b''
        for i, fi in enumerate(c.files):
            rel = (fi['dir'] + '/' + fi['name']).strip('/')
            _prog(progress, i, n, rel)
            raw = c.read_raw(fi)
            end = fi['off'] + fi['size']
            npad = (-end) % int(c.hrow.get('Align') or 2048)
            if npad > len(pad_pattern):          # simpan pola padding terpanjang
                c.f.seek(end)
                pad_pattern = c.f.read(npad)
            data = raw
            crila = raw[:8] == b'CRILAYLA'
            if crila:
                data = crilayla(raw)
            ent = {'dir': fi['dir'], 'name': fi['name'], 'id': fi['id'],
                   'orig_off': fi['off'], 'orig_size': fi['size'],
                   'orig_esize': fi['esize'], 'crila': crila}
            if decode and is_wesys(data):
                try:
                    data, info = wesys_decode(data)
                    ent['wesys'] = info; n_dec += 1
                except Exception:
                    n_fail += 1
            p = _safe_join(outdir, fi['dir'], fi['name'])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'wb') as out:
                out.write(data)
            ent['md5'] = _md5(data)
            entries.append(ent)
        # padding header & TOC (supaya hasil susun ulang identik dengan aslinya)
        c.f.seek(16 + c.hdr_len)
        hdr_pad = c.f.read(c.hrow['TocOffset'] - 6 - 16 - c.hdr_len)
        toc_end = c.hrow['TocOffset'] + 16 + c.toc_len
        c.f.seek(toc_end)
        toc_pad = c.f.read(max(0, (c.hrow.get('ContentOffset') or toc_end) - toc_end))
        man = {
            'version': 1,
            'source_name': os.path.basename(cpk_path),
            'source_size': os.path.getsize(cpk_path),
            'magic_pad': c.magic_pad.hex(), 'toc_pad4': c.toc_pad.hex(),
            'hdr_encrypted': c.hdr.encrypted, 'toc_encrypted': c.toc.encrypted,
            'hdr_name': c.hdr.name, 'toc_name': c.toc.name,
            'hdr_cols': _cols_to_json(c.hdr.cols), 'hdr_row': _row_to_json(c.hrow),
            'toc_cols': _cols_to_json(c.toc.cols),
            'hdr_pad': _b64(hdr_pad), 'toc_pad': _b64(toc_pad),
            'pad_pattern': _b64(pad_pattern),
            'files': entries,
        }
    with open(os.path.join(outdir, MANIFEST), 'w', encoding='utf-8') as f:
        json.dump(man, f)
    _prog(progress, n, n, 'selesai')
    return {'files': n, 'decoded': n_dec, 'failed': n_fail, 'outdir': outdir}


# ---------------------------------------------------------------- BUILD
def build(folder, out_path, original=None, progress=None):
    """Susun CPK dari folder hasil bongkar.
    original: CPK asli (opsional). File yang tidak diubah disalin utuh dari
    sana sehingga hasilnya persis sama dengan aslinya."""
    mpath = os.path.join(folder, MANIFEST)
    if not os.path.isfile(mpath):
        raise CpkError('Folder ini bukan hasil bongkar aplikasi ini '
                       '(file %s tidak ada).' % MANIFEST)
    with open(mpath, encoding='utf-8') as f:
        man = json.load(f)
    align = int(_row_from_json(man['hdr_row']).get('Align') or 2048)
    pattern = _unb64(man.get('pad_pattern'))

    orig = None
    if original:
        if os.path.getsize(original) != man['source_size']:
            raise CpkError('CPK asli yang dipilih ukurannya berbeda dari CPK yang '
                           'dulu dibongkar. Pilih file CPK yang benar.')
        orig = open(original, 'rb')

    try:
        # --- kumpulkan entri
        ents, known = [], set()
        for e in man['files']:
            rel = (e['dir'] + '/' + e['name']).strip('/')
            known.add(rel)
            p = _safe_join(folder, e['dir'], e['name'])
            if not os.path.isfile(p):
                continue                      # file dihapus -> tidak dimasukkan
            ents.append(dict(e, path=p, rel=rel, new=False))
        next_id = max([e['id'] or 0 for e in man['files']] + [-1]) + 1
        for root, dirs, names in os.walk(folder):
            dirs[:] = [d for d in dirs if d != '_cpk_backup']
            for nm in sorted(names):
                if nm == MANIFEST or nm.endswith('.tmp'):
                    continue
                full = os.path.join(root, nm)
                rel = os.path.relpath(full, folder).replace(os.sep, '/')
                if rel in known:
                    continue
                d, _, n2 = rel.rpartition('/')
                ents.append({'dir': d, 'name': n2, 'id': next_id, 'path': full,
                             'rel': rel, 'new': True})
                next_id += 1
        if not ents:
            raise CpkError('Folder kosong, tidak ada file untuk dimasukkan.')
        toc_order = sorted(ents, key=lambda e: e['rel'])
        data_order = sorted(ents, key=lambda e: e['id'])

        hdr_cols = _cols_from_json(man['hdr_cols'])
        hrow = _row_from_json(man['hdr_row'])
        toc_cols = _cols_from_json(man['toc_cols'])
        hdr_enc, toc_enc = man['hdr_encrypted'], man['toc_encrypted']

        def toc_rows():
            rows = []
            for e in toc_order:
                rows.append({'DirName': e['dir'], 'FileName': e['name'],
                             'FileSize': e.get('size', 0), 'ExtractSize': e.get('esize', 0),
                             'FileOffset': e.get('rel_off', 0), 'ID': e['id'],
                             'UserString': '<NULL>'})
            return rows

        toc_tbl = utf_build(man['toc_name'], toc_cols, toc_rows(), toc_enc)
        hdr_tbl = utf_build(man['hdr_name'], hdr_cols, [hrow], hdr_enc)
        toc_off = hrow['TocOffset']
        need = 16 + len(hdr_tbl) + 6
        if need > toc_off:
            toc_off = -(-need // align) * align
        content_off = -(-(toc_off + 16 + len(toc_tbl)) // align) * align

        # --- tulis data file dulu (urut ID)
        tmp = out_path + '.part'
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        n = len(data_order)
        stats = {'files': n, 'reused': 0, 'reencoded': 0, 'added': 0, 'removed':
                 len(man['files']) - sum(1 for e in ents if not e['new'])}
        with open(tmp, 'wb') as out:
            out.seek(content_off)
            pos = content_off
            sum_packed = sum_data = 0
            for i, e in enumerate(data_order):
                _prog(progress, i, n, e['rel'])
                blob = None
                if not e['new'] and orig is not None and e.get('md5') == _md5_file(e['path']):
                    orig.seek(e['orig_off'])
                    blob = orig.read(e['orig_size'])
                    e['size'], e['esize'] = e['orig_size'], e['orig_esize']
                    stats['reused'] += 1
                else:
                    with open(e['path'], 'rb') as f:
                        data = f.read()
                    if e.get('wesys'):
                        blob = wesys_encode(data, e['wesys'])
                        stats['reencoded'] += 1
                    else:
                        blob = data
                        if e['new']:
                            stats['added'] += 1
                    e['size'] = e['esize'] = len(blob)
                e['rel_off'] = pos - toc_off
                out.write(blob)
                pos += len(blob)
                sum_packed += e['size']; sum_data += e['esize']
                if i != n - 1:
                    npad = (-pos) % align
                    if npad:
                        out.write(pattern[:npad] if len(pattern) >= npad else b'\x00' * npad)
                        pos += npad
            end_aligned = -(-pos // align) * align
            # --- isi header
            hrow.update({'ContentOffset': content_off, 'ContentSize': end_aligned - content_off,
                         'TocOffset': toc_off, 'TocSize': 16 + len(toc_tbl),
                         'EnabledPackedSize': sum_packed, 'EnabledDataSize': sum_data,
                         'Files': n})
            hdr_tbl = utf_build(man['hdr_name'], hdr_cols, [hrow], hdr_enc)
            toc_tbl = utf_build(man['toc_name'], toc_cols, toc_rows(), toc_enc)
            out.seek(0)
            out.write(b'CPK ' + bytes.fromhex(man['magic_pad']) +
                      struct.pack('<Q', len(hdr_tbl)) + hdr_tbl)
            hp = _unb64(man.get('hdr_pad'))
            gap = toc_off - 6 - out.tell()
            out.write(hp[:gap] + b'\x00' * max(0, gap - len(hp)))
            out.write(b'(c)CRI')
            out.write(b'TOC ' + bytes.fromhex(man['toc_pad4']) +
                      struct.pack('<Q', len(toc_tbl)) + toc_tbl)
            tp = _unb64(man.get('toc_pad'))
            gap = content_off - out.tell()
            out.write(tp[:gap] + b'\x00' * max(0, gap - len(tp)))
        # --- cek hasil
        try:
            chk = list_cpk(tmp)
            assert len(chk) == n
        except Exception as ex:
            os.remove(tmp)
            raise CpkError('Hasil susunan gagal diperiksa: %s' % ex)
        if os.path.exists(out_path):
            os.remove(out_path)
        os.rename(tmp, out_path)
    finally:
        if orig:
            orig.close()
    _prog(progress, n, n, 'selesai')
    stats['out'] = out_path
    stats['size'] = os.path.getsize(out_path)
    return stats


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == 'list':
        for x in list_cpk(a[1]):
            print(('%s/%s' % (x['dir'], x['name'])).strip('/'), x['size'])
    elif len(a) >= 2 and a[0] == 'extract':
        print(extract(a[1], a[2] if len(a) > 2 else 'cpk_out',
                      lambda i, n, m: print('%d/%d %s' % (i, n, m))))
    elif len(a) >= 3 and a[0] == 'build':
        print(build(a[1], a[2], a[3] if len(a) > 3 else None))
    else:
        print('Pemakaian:\n  python3 cpk_core.py list <file.cpk>\n'
              '  python3 cpk_core.py extract <file.cpk> <folder>\n'
              '  python3 cpk_core.py build <folder> <baru.cpk> [asli.cpk]')
