#!/usr/bin/env python3
"""Lokaler Instagram-Link-Sammler. Nur Python-Standardbibliothek."""
import csv
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

URL_RE = re.compile(r'https?://[^\s<>"\'\\]+', re.I)
INSTAGRAM_HOSTS = {'instagram.com', 'www.instagram.com', 'm.instagram.com', 'instagr.am', 'www.instagr.am'}
FIELDS = ['Bereich', 'Chat', 'Absender_oder_Account', 'Datum', 'Typ', 'URL', 'Quelldatei']

def normalize_url(raw):
    raw = raw.replace('\\/', '/').replace('\\u0026', '&').rstrip('.,;:!?)]}')
    try:
        parts = urlsplit(raw)
        if parts.scheme not in ('http', 'https') or not parts.netloc:
            return ''
        return urlunsplit(('https', parts.netloc.lower(), parts.path.rstrip('/') or '/', parts.query, ''))
    except ValueError:
        return ''

def get_urls(value):
    if not isinstance(value, str):
        return []
    out = []
    for match in URL_RE.findall(value):
        url = normalize_url(match)
        if url and url not in out:
            out.append(url)
    return out

def classify(url):
    parts = urlsplit(url)
    if (parts.hostname or '').lower() not in INSTAGRAM_HOSTS:
        return 'Externer Link'
    path = parts.path.lower()
    if path.startswith('/reel/') or path.startswith('/reels/'):
        return 'Reel'
    if path.startswith('/p/'):
        return 'Post'
    if path.startswith('/stories/'):
        return 'Story'
    if path.startswith('/tv/'):
        return 'Video'
    return 'Instagram-Link'

def area_of(path):
    p = path.lower().replace('\\', '/')
    if '/messages/' in '/' + p or p.startswith('messages/'):
        return 'Chat'
    if 'saved' in p or 'gespeichert' in p or 'collection' in p:
        return 'Gespeichert'
    if 'archive' in p or 'archiv' in p or 'stories' in p or '/posts/' in p:
        return 'Archiv/eigene Inhalte'
    return 'Sonstiges'

def chat_of(path):
    bits = path.replace('\\', '/').split('/')
    for ix, bit in enumerate(bits):
        if bit.lower() == 'inbox' and ix + 1 < len(bits):
            return bits[ix + 1]
    return Path(path).parent.name if area_of(path) == 'Chat' else ''

def date_of(item):
    if not isinstance(item, dict):
        return ''
    for k in ('timestamp_ms', 'timestamp', 'creation_timestamp', 'saved_at', 'date', 'time'):
        v = item.get(k)
        if isinstance(v, (int, float)):
            try:
                secs = v / 1000 if v > 1e11 else v
                return datetime.fromtimestamp(secs, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            except (ValueError, OSError, OverflowError):
                continue
        if isinstance(v, str):
            return v
    return ''

def sender_of(item):
    if not isinstance(item, dict):
        return ''
    for k in ('sender_name', 'sender', 'username', 'title', 'author'):
        val = item.get(k)
        if isinstance(val, str):
            return val
    return ''

def extract_json(doc, path):
    area = area_of(path)
    chat = chat_of(path)
    found = []
    def visit(node, sender='', date=''):
        if isinstance(node, dict):
            sender = sender_of(node) or sender
            date = date_of(node) or date
            for key, val in node.items():
                if isinstance(val, str):
                    for url in get_urls(val):
                        found.append({'Bereich': area, 'Chat': chat, 'Absender_oder_Account': sender,
                                      'Datum': date, 'Typ': classify(url), 'URL': url, 'Quelldatei': path})
                else:
                    visit(val, sender, date)
        elif isinstance(node, list):
            for val in node:
                visit(val, sender, date)
    visit(doc)
    return found

def scan_export(path):
    source = Path(path)
    if source.suffix.lower() == '.zip':
        with zipfile.ZipFile(source) as z:
            infos = [x for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith('.json')]
            if len(infos) > 20000:
                raise ValueError('Ungewöhnlich viele JSON-Dateien im ZIP.')
            rows = []
            errors = 0
            for info in infos:
                if info.file_size > 120_000_000:
                    errors += 1
                    continue
                try:
                    doc = json.loads(z.read(info).decode('utf-8-sig'))
                    rows.extend(extract_json(doc, info.filename))
                except (ValueError, UnicodeError, RuntimeError, zipfile.BadZipFile):
                    errors += 1
            return dedupe(rows), len(infos), errors
    if source.suffix.lower() == '.json':
        doc = json.loads(source.read_text(encoding='utf-8-sig'))
        return dedupe(extract_json(doc, source.name)), 1, 0
    raise ValueError('Bitte eine ZIP- oder JSON-Datei auswählen.')

def dedupe(rows):
    seen = set()
    unique = []
    for row in rows:
        key = (row['Bereich'], row['Chat'], row['URL'])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return sorted(unique, key=lambda r: (r['Bereich'], r['Chat'], r['Datum'], r['URL']))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Instagram-Link-Sammler · lokal & privat')
        self.geometry('1030x660')
        self.minsize(780, 480)
        self.rows = []
        root = ttk.Frame(self, padding=16)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='Instagram-Link-Sammler', font=('Arial', 18, 'bold')).pack(anchor='w')
        ttk.Label(root, text='Liest deinen JSON-Export lokal. Keine Anmeldung, kein Upload, keine Änderung an Instagram.').pack(anchor='w', pady=(2,12))
        filebar = ttk.Frame(root)
        filebar.pack(fill='x', pady=(0,10))
        self.file_label = ttk.Label(filebar, text='Noch keine Datei ausgewählt')
        self.file_label.pack(side='left', fill='x', expand=True)
        ttk.Button(filebar, text='ZIP oder JSON öffnen', command=self.open).pack(side='right')
        filterbar = ttk.Frame(root)
        filterbar.pack(fill='x', pady=(0,8))
        ttk.Label(filterbar, text='Bereich:').pack(side='left')
        self.area = ttk.Combobox(filterbar, state='readonly', width=23, values=['Alle', 'Chat', 'Gespeichert', 'Archiv/eigene Inhalte', 'Sonstiges'])
        self.area.set('Alle'); self.area.pack(side='left', padx=(6,20))
        self.area.bind('<<ComboboxSelected>>', lambda event: self.refresh())
        ttk.Label(filterbar, text='Chat:').pack(side='left')
        self.chat = ttk.Combobox(filterbar, state='readonly', width=31, values=['Alle Chats'])
        self.chat.set('Alle Chats'); self.chat.pack(side='left', padx=(6,20))
        self.chat.bind('<<ComboboxSelected>>', lambda event: self.refresh())
        self.ig_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(filterbar, text='Nur Instagram-Links', variable=self.ig_only, command=self.refresh).pack(side='left')
        self.status = ttk.Label(root, text='Bitte einen Instagram-Export im JSON-Format auswählen.')
        self.status.pack(anchor='w', pady=(2,8))
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(frame, columns=FIELDS, show='headings')
        widths = [135, 155, 150, 160, 110, 350, 200]
        for col, w in zip(FIELDS, widths):
            self.table.heading(col, text=col.replace('_', ' '))
            self.table.column(col, width=w, minwidth=70, stretch=(col == 'URL'))
        yscroll = ttk.Scrollbar(frame, command=self.table.yview)
        xscroll = ttk.Scrollbar(frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        bar = ttk.Frame(root)
        bar.pack(fill='x', pady=(12,0))
        ttk.Button(bar, text='Markierten Link kopieren', command=self.copy).pack(side='left')
        ttk.Button(bar, text='Gefilterte Links als CSV exportieren', command=self.export).pack(side='right')
        ttk.Label(root, text='Hinweis: Nur im Export vorhandene URLs sind auffindbar. Fehlende Reel-Links können nicht rekonstruiert werden.', foreground='#666').pack(anchor='w', pady=(10,0))
    def open(self):
        selected = filedialog.askopenfilename(title='Instagram-Export wählen', filetypes=[('Instagram-Daten', '*.zip *.json'), ('ZIP-Datei', '*.zip'), ('JSON-Datei', '*.json')])
        if not selected:
            return
        try:
            self.rows, total, errors = scan_export(selected)
        except Exception as exc:
            messagebox.showerror('Datei konnte nicht gelesen werden', str(exc)); return
        self.file_label.configure(text=selected)
        chats = sorted(set(row['Chat'] for row in self.rows if row['Bereich'] == 'Chat' and row['Chat']))
        self.chat.configure(values=['Alle Chats'] + chats)
        self.chat.set('Alle Chats')
        self.area.set('Alle')
        self.refresh()
        if errors:
            messagebox.showwarning('Hinweis', f'{errors} von {total} JSON-Dateien konnten nicht gelesen werden.')
    def filtered(self):
        result = self.rows
        if self.area.get() != 'Alle':
            result = [r for r in result if r['Bereich'] == self.area.get()]
        if self.chat.get() != 'Alle Chats':
            result = [r for r in result if r['Chat'] == self.chat.get()]
        if self.ig_only.get():
            result = [r for r in result if r['Typ'] != 'Externer Link']
        return result
    def refresh(self):
        self.table.delete(*self.table.get_children())
        rows = self.filtered()
        for row in rows[:10000]:
            self.table.insert('', 'end', values=[row[k] for k in FIELDS])
        self.status.configure(text=f'{len(rows)} Links in aktueller Ansicht · {len(self.rows)} insgesamt (Duplikate je Bereich und Chat entfernt)' + (' · Vorschau auf 10.000 begrenzt' if len(rows)>10000 else ''))
    def copy(self):
        current = self.table.selection()
        if current:
            url = self.table.item(current[0], 'values')[5]
            self.clipboard_clear(); self.clipboard_append(url)
            self.status.configure(text='Link in die Zwischenablage kopiert.')
    def export(self):
        rows = self.filtered()
        if not rows:
            messagebox.showinfo('Keine Links', 'In der aktuellen Auswahl wurden keine Links gefunden.'); return
        selected = filedialog.asksaveasfilename(title='Linkliste speichern', defaultextension='.csv', initialfile='instagram_links.csv', filetypes=[('CSV (Excel-kompatibel)', '*.csv')])
        if not selected:
            return
        with open(selected, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=';')
            writer.writeheader(); writer.writerows(rows)
        messagebox.showinfo('CSV gespeichert', f'{len(rows)} Links gespeichert:\n{selected}')

if __name__ == '__main__':
    App().mainloop()
