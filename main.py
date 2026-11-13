# -*- coding: utf-8 -*-
"""CPK Tool eFootball - bongkar & susun file .cpk dengan tampilan sederhana."""
import os, json, threading, traceback
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform

import cpk_core as core

Window.clearcolor = (0.08, 0.09, 0.12, 1)
ON_ANDROID = platform == 'android'
START_DIR = '/storage/emulated/0' if ON_ANDROID else os.path.expanduser('~')


# ------------------------------------------------------------ izin Android
def has_all_files():
    if not ON_ANDROID:
        return True
    try:
        from jnius import autoclass
        if autoclass('android.os.Build$VERSION').SDK_INT >= 30:
            return bool(autoclass('android.os.Environment').isExternalStorageManager())
    except Exception:
        pass
    return True

def request_all_files():
    if not ON_ANDROID:
        return
    try:
        from jnius import autoclass
        if autoclass('android.os.Build$VERSION').SDK_INT >= 30:
            Intent = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            Uri = autoclass('android.net.Uri')
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            it = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            it.setData(Uri.parse('package:' + act.getPackageName()))
            act.startActivity(it)
        else:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                 Permission.WRITE_EXTERNAL_STORAGE])
    except Exception:
        traceback.print_exc()


def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return ('%d %s' % (n, u)) if u == 'B' else ('%.1f %s' % (n, u))
        n /= 1024.0


KV = '''
#:import dp kivy.metrics.dp

<Btn@Button>:
    font_size: '17sp'
    size_hint_y: None
    height: dp(56)
    background_normal: ''
    background_color: 0.18, 0.21, 0.30, 1
    color: 1, 1, 1, 1

<BigBtn@Button>:
    font_size: '19sp'
    bold: True
    size_hint_y: None
    height: dp(84)
    background_normal: ''
    halign: 'center'
    valign: 'middle'
    text_size: self.width - dp(24), None
    color: 1, 1, 1, 1

<Txt@Label>:
    color: 0.92, 0.94, 0.98, 1
    font_size: '15sp'
    size_hint_y: None
    text_size: self.width, None
    height: self.texture_size[1] + dp(6)
    halign: 'left'
    valign: 'top'

<Card@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(14)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: 0.14, 0.16, 0.22, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]

<HomeScreen>:
    name: 'home'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(18)
        spacing: dp(14)
        Txt:
            text: 'CPK Tool eFootball'
            font_size: '26sp'
            bold: True
            halign: 'center'
        Txt:
            text: 'Buka, ubah, dan susun kembali file .cpk dengan mudah.'
            halign: 'center'
            color: 0.7, 0.75, 0.85, 1
        Card:
            id: perm
            opacity: 1 if root.need_perm else 0
            height: self.minimum_height if root.need_perm else 0
            disabled: not root.need_perm
            Txt:
                text: 'Aplikasi butuh izin "Akses semua file" supaya bisa membaca & menyimpan file CPK.'
            Btn:
                text: 'Beri izin akses file'
                background_color: 0.85, 0.45, 0.1, 1
                on_release: app.ask_permission()
        BigBtn:
            text: '1. BONGKAR CPK\\n(pecah jadi banyak file)'
            background_color: 0.12, 0.55, 0.35, 1
            on_release: app.root.current = 'extract'
        BigBtn:
            text: '2. SUSUN CPK\\n(gabung lagi jadi satu .cpk)'
            background_color: 0.15, 0.40, 0.75, 1
            on_release: app.root.current = 'build'
        Btn:
            text: 'Cara pakai'
            on_release: app.show_help()
        Widget:

<ExtractScreen>:
    name: 'extract'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(14)
        spacing: dp(10)
        Txt:
            text: 'Bongkar CPK'
            font_size: '22sp'
            bold: True
        Card:
            Txt:
                text: 'Langkah 1: pilih file .cpk'
                bold: True
            Btn:
                text: 'Pilih file CPK'
                on_release: root.pick_cpk()
            Txt:
                text: root.cpk_text
                color: 0.6, 0.9, 0.7, 1
        Card:
            Txt:
                text: 'Hasil akan disimpan di folder:'
            Txt:
                text: root.out_text
                color: 0.6, 0.8, 1, 1
        BigBtn:
            text: 'MULAI BONGKAR'
            background_color: 0.12, 0.55, 0.35, 1
            disabled: root.busy or not root.cpk_path
            on_release: root.start()
        ProgressBar:
            max: 100
            value: root.percent
            size_hint_y: None
            height: dp(14)
        ScrollView:
            Txt:
                text: root.log
        Btn:
            text: 'Kembali'
            on_release: app.root.current = 'home'

<BuildScreen>:
    name: 'build'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(14)
        spacing: dp(10)
        Txt:
            text: 'Susun CPK'
            font_size: '22sp'
            bold: True
        Card:
            Txt:
                text: 'Langkah 1: pilih FOLDER hasil bongkar'
                bold: True
            Btn:
                text: 'Pilih folder'
                on_release: root.pick_folder()
            Txt:
                text: root.folder_text
                color: 0.6, 0.9, 0.7, 1
        Card:
            Txt:
                text: 'Langkah 2 (disarankan): pilih CPK asli'
                bold: True
            Txt:
                text: 'Supaya file yang tidak kamu ubah disalin persis seperti aslinya.'
                font_size: '13sp'
                color: 0.7, 0.75, 0.85, 1
            Btn:
                text: 'Pilih CPK asli'
                on_release: root.pick_original()
            Txt:
                text: root.orig_text
                color: 0.6, 0.9, 0.7, 1
        Card:
            Txt:
                text: 'Langkah 3: nama CPK baru'
                bold: True
            TextInput:
                id: outname
                text: root.out_name
                on_text: root.out_name = self.text
                multiline: False
                size_hint_y: None
                height: dp(46)
                font_size: '16sp'
        BigBtn:
            text: 'MULAI SUSUN'
            background_color: 0.15, 0.40, 0.75, 1
            disabled: root.busy or not root.folder
            on_release: root.start()
        ProgressBar:
            max: 100
            value: root.percent
            size_hint_y: None
            height: dp(14)
        ScrollView:
            Txt:
                text: root.log
        Btn:
            text: 'Kembali'
            on_release: app.root.current = 'home'
'''


# ------------------------------------------------------------ pemilih file/folder
class Picker(Popup):
    """Jendela untuk memilih file (mode 'file') atau folder (mode 'folder')."""
    def __init__(self, mode, callback, start=None, exts=(), title='', **kw):
        super().__init__(title=title or ('Pilih folder' if mode == 'folder' else 'Pilih file'),
                         size_hint=(0.96, 0.92), auto_dismiss=True, **kw)
        self.mode, self.callback, self.exts = mode, callback, tuple(exts)
        self.path = start if start and os.path.isdir(start) else START_DIR
        root = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(6))
        self.lbl = Label(size_hint_y=None, height=dp(44), font_size='13sp',
                         halign='left', valign='middle', color=(0.7, 0.9, 1, 1))
        self.lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))
        root.add_widget(self.lbl)
        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        up = Button(text='< Naik', background_normal='', background_color=(0.25, 0.28, 0.38, 1))
        up.bind(on_release=lambda *_: self.go(os.path.dirname(self.path.rstrip('/')) or '/'))
        home = Button(text='Awal', background_normal='', background_color=(0.25, 0.28, 0.38, 1))
        home.bind(on_release=lambda *_: self.go(START_DIR))
        bar.add_widget(up); bar.add_widget(home)
        if mode == 'folder':
            ok = Button(text='Pilih folder ini', bold=True, background_normal='',
                        background_color=(0.12, 0.55, 0.35, 1))
            ok.bind(on_release=lambda *_: self.choose(self.path))
            bar.add_widget(ok)
        root.add_widget(bar)
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        self.sv = ScrollView()
        self.grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.sv.add_widget(self.grid)
        root.add_widget(self.sv)
        self.content = root
        self.go(self.path)

    def go(self, path):
        self.path = path
        self.lbl.text = path
        self.grid.clear_widgets()
        try:
            names = sorted(os.listdir(path), key=lambda s: s.lower())
        except Exception:
            self.grid.add_widget(Label(text='Folder ini tidak bisa dibuka.\n(Cek izin akses file)',
                                       size_hint_y=None, height=dp(70)))
            return
        shown = 0
        for nm in names:
            full = os.path.join(path, nm)
            isdir = os.path.isdir(full)
            if nm.startswith('.'):
                continue
            if not isdir and (self.mode == 'folder' or
                              (self.exts and not nm.lower().endswith(self.exts))):
                continue
            shown += 1
            b = Button(text=('[ folder ]  ' if isdir else '') + nm, size_hint_y=None,
                       height=dp(52), halign='left', valign='middle', font_size='15sp',
                       background_normal='', shorten=True, shorten_from='right',
                       background_color=(0.2, 0.24, 0.34, 1) if isdir else (0.16, 0.36, 0.28, 1))
            b.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(16), None)))
            b.bind(on_release=lambda w, f=full, d=isdir: self.go(f) if d else self.choose(f))
            self.grid.add_widget(b)
        if not shown:
            self.grid.add_widget(Label(text='(kosong)', size_hint_y=None, height=dp(50)))

    def choose(self, p):
        self.dismiss()
        self.callback(p)


# ------------------------------------------------------------ layar dasar kerja
class WorkScreen(Screen):
    log = StringProperty('')
    percent = NumericProperty(0)
    busy = BooleanProperty(False)

    def say(self, text, replace=False):
        self.log = text if replace else (self.log + ('\n' if self.log else '') + text)

    def run_bg(self, fn, on_done):
        self.busy = True; self.percent = 0
        def work():
            try:
                res = fn(self._progress)
                Clock.schedule_once(lambda dt: self._finish(on_done, res, None))
            except Exception as e:
                tb = traceback.format_exc()
                Clock.schedule_once(lambda dt: self._finish(on_done, None, (e, tb)))
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, i, n, msg):
        def ui(dt):
            self.percent = (100.0 * i / n) if n else 0
            self.say('(%d/%d) %s' % (i, n, msg) if msg != 'selesai' else 'Selesai...', )
            # jaga log tetap pendek
            lines = self.log.split('\n')
            if len(lines) > 6:
                self.log = '\n'.join(lines[-6:])
        Clock.schedule_once(ui)

    def _finish(self, on_done, res, err):
        self.busy = False
        if err:
            e, tb = err
            msg = str(e) if isinstance(e, core.CpkError) else \
                'Terjadi kesalahan: %s' % e
            self.percent = 0
            self.say('GAGAL\n' + msg, replace=True)
            if not isinstance(e, core.CpkError):
                print(tb)
        else:
            self.percent = 100
            on_done(res)


class HomeScreen(Screen):
    need_perm = BooleanProperty(False)


class ExtractScreen(WorkScreen):
    cpk_path = StringProperty('')
    cpk_text = StringProperty('Belum ada file dipilih.')
    out_text = StringProperty('-')

    def pick_cpk(self):
        start = os.path.dirname(self.cpk_path) if self.cpk_path else None
        Picker('file', self.set_cpk, start, exts=('.cpk',), title='Pilih file .cpk').open()

    def set_cpk(self, p):
        self.cpk_path = p
        base = os.path.splitext(os.path.basename(p))[0]
        self.out_dir = os.path.join(os.path.dirname(p), base + '_hasil')
        self.cpk_text = '%s  (%s)' % (os.path.basename(p), human(os.path.getsize(p)))
        self.out_text = self.out_dir
        self.say('', replace=True); self.percent = 0

    def start(self):
        self.say('Membongkar...', replace=True)
        cpk, out = self.cpk_path, self.out_dir
        def done(r):
            txt = ('SELESAI!\n%d file dibongkar (%d file game sudah didekode).\n'
                   'Folder hasil:\n%s\n\nEdit file di dalamnya, lalu pakai menu '
                   '"SUSUN CPK".\nJangan hapus file _cpk_manifest.json.'
                   % (r['files'], r['decoded'], r['outdir']))
            if r['failed']:
                txt += '\n(%d file gagal didekode, disimpan apa adanya)' % r['failed']
            self.say(txt, replace=True)
        self.run_bg(lambda cb: core.extract(cpk, out, cb), done)


class BuildScreen(WorkScreen):
    folder = StringProperty('')
    folder_text = StringProperty('Belum ada folder dipilih.')
    orig = StringProperty('')
    orig_text = StringProperty('Belum dipilih (boleh dilewati).')
    out_name = StringProperty('')

    def pick_folder(self):
        start = os.path.dirname(self.folder) if self.folder else None
        Picker('folder', self.set_folder, start, title='Pilih folder hasil bongkar').open()

    def set_folder(self, p):
        mp = os.path.join(p, core.MANIFEST)
        if not os.path.isfile(mp):
            self.folder = ''
            self.folder_text = 'Folder ini BUKAN hasil bongkar dari aplikasi ini\n(file _cpk_manifest.json tidak ada).'
            return
        self.folder = p
        self.folder_text = p
        try:
            man = json.load(open(mp, encoding='utf-8'))
            src = man.get('source_name', 'hasil.cpk')
            size = man.get('source_size')
        except Exception:
            src, size = 'hasil.cpk', None
        stem = os.path.splitext(src)[0]
        self.out_name = stem + '_BARU.cpk'
        self.orig, self.orig_text = '', 'Belum dipilih (boleh dilewati).'
        guess = os.path.join(os.path.dirname(p.rstrip('/')), src)
        if os.path.isfile(guess) and (size is None or os.path.getsize(guess) == size):
            self.set_orig(guess)
        self.say('', replace=True); self.percent = 0

    def pick_original(self):
        start = os.path.dirname(self.folder) if self.folder else None
        Picker('file', self.set_orig, start, exts=('.cpk',), title='Pilih CPK asli').open()

    def set_orig(self, p):
        self.orig = p
        self.orig_text = os.path.basename(p)

    def start(self):
        name = (self.out_name or 'hasil_BARU.cpk').strip()
        if not name.lower().endswith('.cpk'):
            name += '.cpk'
        out = os.path.join(os.path.dirname(self.folder.rstrip('/')), name)
        folder, orig = self.folder, self.orig or None
        self.say('Menyusun...', replace=True)
        def done(r):
            self.say('SELESAI!\nCPK baru (%s):\n%s\n\n'
                     'File tidak diubah (disalin asli): %d\nDikodekan ulang: %d\n'
                     'Ditambah: %d   Dihapus: %d'
                     % (human(r['size']), r['out'], r['reused'], r['reencoded'],
                        r['added'], r['removed']), replace=True)
        self.run_bg(lambda cb: core.build(folder, out, orig, cb), done)


HELP = (
    'BONGKAR (membuka CPK)\n'
    '1. Salin file .cpk ke memori HP (mis. folder Download).\n'
    '2. Tekan "Bongkar CPK" > pilih file > "Mulai bongkar".\n'
    '3. Hasilnya ada di folder bernama <nama>_hasil di tempat yang sama.\n\n'
    'SUSUN (menjadikan CPK lagi)\n'
    '1. Edit/ganti file di folder hasil (nama file jangan diubah).\n'
    '2. Tekan "Susun CPK" > pilih folder hasil > (pilih CPK asli) > "Mulai susun".\n'
    '3. Hasil: <nama>_BARU.cpk. Ganti nama sesuai aslinya saat menaruhnya di game.\n\n'
    'Tips: SIMPAN CADANGAN file CPK asli sebelum menimpanya di game.\n'
    'File yang ditambahkan ke folder otomatis ikut dimasukkan; file yang dihapus '
    'tidak ikut.')


class CpkApp(App):
    title = 'CPK Tool eFootball'

    def build(self):
        Builder.load_string(KV)
        self.sm = ScreenManager()
        self.home = HomeScreen()
        self.sm.add_widget(self.home)
        self.sm.add_widget(ExtractScreen())
        self.sm.add_widget(BuildScreen())
        self.home.need_perm = not has_all_files()
        Window.bind(on_keyboard=self.on_key)
        return self.sm

    def on_start(self):
        if ON_ANDROID and not has_all_files():
            request_all_files()

    def on_resume(self):
        self.home.need_perm = not has_all_files()

    def ask_permission(self):
        request_all_files()

    def on_key(self, win, key, *a):
        if key == 27:                       # tombol Back Android
            if self.sm.current != 'home':
                self.sm.current = 'home'
                return True
        return False

    def show_help(self):
        lbl = Label(text=HELP, text_size=(Window.width * 0.84, None), halign='left',
                    valign='top', size_hint_y=None, font_size='14sp')
        lbl.bind(texture_size=lambda w, s: setattr(w, 'height', s[1] + dp(10)))
        from kivy.uix.scrollview import ScrollView
        sv = ScrollView(); sv.add_widget(lbl)
        Popup(title='Cara pakai', content=sv, size_hint=(0.94, 0.85)).open()


# properti out_dir dipakai ExtractScreen
ExtractScreen.out_dir = ''

if __name__ == '__main__':
    CpkApp().run()
