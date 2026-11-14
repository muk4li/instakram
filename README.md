# instakram ✦

Eine **lokale Instagram-Link-Bibliothek** mit Browseroberfläche. Sammelt URLs aus privaten Chats, gespeicherten Reels/Posts und Archivdaten des offiziellen Instagram-Datenexports – **ohne Instagram-Anmeldung**, nur Python-Standardbibliothek und SQLite.

**Status:** Beta. Noch nicht an einem realen großen Instagram-Export end-to-end getestet. Aktueller Stand und Backlog: [`aktuellerStand.md`](aktuellerStand.md), [`TASKS.md`](TASKS.md); Entwicklungsregeln: [`AGENTS.md`](AGENTS.md).

## Schnellstart

1. Python 3 installieren (keine weiteren Pakete nötig), Repository klonen.
2. Im Repository-Ordner starten: `python server.py` (unter macOS/Linux ggf. `python3`).
3. Der Browser öffnet **http://127.0.0.1:8765** (sonst manuell öffnen).
4. Instagram-Datenexport als **ZIP oder JSON** per Drag-and-drop importieren.

**Export anfordern:** Instagram → Kontenübersicht → Deine Informationen und Berechtigungen → Informationen exportieren. Format **JSON**, gesamter Zeitraum, gewünschte Kategorien.

## Funktionen

- **Bibliothek:** Kachel- und Listenansicht; Suche nach Link, Chat, Absender und Dateiname; Filter nach Chat, gespeichert, Archiv und Inhaltstyp (Reel, Post, Story, sonstige URL); Excel-kompatibler CSV-Export aller gefilterten Treffer.
- **Kodierungskorrektur:** Instagram-Exporte speichern Umlaute/Emojis fehlerhaft kodiert (z. B. „JÃ¼rgen“). Absender, Beschreibungen, Hashtags und Creator werden beim Import zu „Jürgen“ repariert; bestehende Datenbanken einmalig beim Start (ohne Duplikate, Zuordnungen bleiben erhalten).
- **Ordner & Gruppen:** Eigene Ordner und Unterordner (anlegen, umbenennen, löschen), Mehrfachzuordnung je Link. Standardgruppen unter `groups/`: Tech & KI, Programmieren, Gaming, Memes & Humor, Musik, Wissen & Bildung, Favoriten, Fitness & Sport, Design & Kunst, Lifestyle, Inspiration, Rezepte, Anime, Filme und Serien.
- **Regeln:** Gruppe + Feld (URL, Absender, Chat, Typ, Bereich, Quelldatei, Beschreibung/Hashtag) + Suchbegriff; gilt auch für bereits importierte Links. Beim Entfernen einer Regel bleiben vorhandene Zuordnungen bestehen.
- **Posteingang:** Neue Links prüfen, Ordner bestätigen, „Später prüfen“ (zählt nicht als Ablehnung) oder „Erneut prüfen“. Bestätigungen werden lokal als Feedback gespeichert. Für Instagram-Profilnamen in der URL und spezifische externe Domains entstehen ab zwei positiven Bestätigungen Vorschläge (Signal 80); ab vier ohne Gegenbeispiel ordnet die Automatik zu (Signal 95), sofern eingeschaltet und Schwelle erreicht. Automatisch zugeordnete Links bleiben bis zur Bestätigung im Posteingang. Automatik und Schwelle sind einstellbar.
- **Vorschläge:** Lokale Stichwort-Vorschläge ohne KI. Optional lokale KI über [Ollama](https://ollama.com/) (Standardmodell `llama3.2`, erreichbar unter `127.0.0.1:11434`): nach Klick und Einwilligung werden **höchstens 20** gefilterte Links (URL und Metadaten) an Ollama auf dem eigenen Rechner geschickt; Ergebnis sind prüfbare Vorschläge, keine automatische Übernahme.
- **Hashtags & Wörter:** Nach Häufigkeit sortierte Hashtags und Schlüsselwörter aus exportierten Beschreibungen (`caption`, `description`, `alt_text`, `accessibility_caption`). Gezählt wird je eindeutiger URL einmal, Groß-/Kleinschreibung vereinheitlicht. Schlüsselwörter: einfache Worthäufigkeit mit deutscher/englischer Stoppwortliste, keine KI.
- **Themencluster:** Hashtag-Themen (≥ 2 Links, stark gemeinsam auftretende Hashtags zusammengefasst), Wort-Themen (≥ 3 Links), Gruppen-Themen (vorhandene `groups/…`-Zuordnungen mit ≥ 2 Links), Creator-Themen (nur explizite Profil-URLs oder Exportfelder `creator_username`, `owner_username`, `media_owner_username`). Ein Link kann in mehreren Clustern stehen. Nach Bestätigung lassen sich höchstens 500 Links eines Clusters einem Ordner zuordnen.
- **Instagram-Einbettungen (optional):** Nur nach ausdrücklicher Zustimmung lädt die App Instagrams offizielles Embed-Skript. Jeder Eintrag hat stets einen „Öffnen“-Link.

## Datenschutz

- Server lauscht nur auf **127.0.0.1:8765** und akzeptiert nur Anfragen mit lokalem Host/Origin. Keine Anmeldung, keine Tokens, keine Cloud-API, kein Scraping, keine Änderungen an Instagram.
- ZIP/JSON wird im Speicher verarbeitet und nicht abgelegt. Die extrahierten Links, Metadaten, Ordner, Regeln und das Feedback werden **dauerhaft in SQLite** gespeichert: `data/instakram.sqlite3` (anderer Ort über Umgebungsvariable `INSTAKRAM_DB`).
- Die SQLite-Datei enthält persönliche Daten: regelmäßig privat sichern, **niemals** ins Repository pushen – ebenso wenig Exporte, ZIP- oder CSV-Dateien.
- Netzwerkverbindungen zu **instagram.com** entstehen erst nach Zustimmung zu den Embeds; dabei können Browser-/Netzwerkdaten an Meta gehen. Ollama-Anfragen gehen nur an den lokalen Rechner.

## Grenzen

- Instagram liefert nicht immer URLs für geteilte Reels; nur tatsächlich enthaltene Links werden erfasst. Archivierte Medien haben nicht unbedingt einen eigenen öffentlichen Link.
- Embeds funktionieren nur für **öffentliche, aktive und dafür freigegebene** Posts/Reels; private, gelöschte, eingeschränkte Posts und Stories nicht.
- Die Zuordnung zu Archiv/gespeichert richtet sich nach Dateipfaden des Exports und kann unvollständig sein.
- Eine Chat-Nachricht mit Reel-Link ist **nicht** die Beschreibung des Reels. Fehlende Beschreibungen werden weder aus dem Netz geladen noch rekonstruiert; Regeln können sie nicht ersetzen.
- Chat-Absender werden nicht als Creator gewertet; Reel-Permalinks enthalten keine verlässliche Creator-ID, fehlende Angaben werden nicht erraten.
- Lernen funktioniert nur für Profil-URLs und spezifische externe Domains, nicht anhand von Reel-IDs oder Absendern. Der Wert 80/95 ist ein **heuristischer Signalwert, keine kalibrierte Wahrscheinlichkeit**.
- Stichwörter, Cluster und KI-Vorschläge sind heuristisch, keine semantische Videoanalyse; unpassende Begriffe sind möglich. Ohne Reel-Inhalt ist jede Erkennung unvollständig. Höchstens 80 Cluster werden angezeigt.
- Große Bibliotheken sind langsam: Jede Aktion lädt die komplette Bibliothek neu. Gemessen mit synthetischen Daten: 100 000 Links ca. 2 s und 55 MB je Aktion, 500 000 Links (z. B. viele Likes) ca. 11 s und 275 MB je Aktion.
- Vorschau auf 80 Kacheln bzw. 500 Zeilen begrenzt; die CSV enthält alle gefilterten Treffer.
- Importlimit 800 MB je Datei, JSON-Einzeldateien max. 150 MB (größere werden übersprungen und als übersprungen gemeldet), alle JSON-Dateien eines ZIP zusammen max. 500 MB (Fotos/Videos im ZIP zählen dafür nicht). Die Datei wird beim Import vollständig in den Arbeitsspeicher geladen; bei 800 MB also entsprechend RAM einplanen.
- Die App kann nichts auf Instagram löschen, entspeichern oder verändern.
- Neue Datenfelder (z. B. Beschreibungen) erscheinen für bereits importierte Links erst nach einem **erneuten Import** desselben Exports; Links werden über ihre URL wiedererkannt, Zuordnungen bleiben erhalten. Schemaänderungen laufen beim Start automatisch – vorher eine Kopie der SQLite-Datei anlegen.

## Projektstruktur

- `server.py` – lokaler HTTP-Server und API
- `parser_core.py` – ZIP/JSON-Parser inkl. Kodierungskorrektur
- `library_db.py` – SQLite-Bibliothek, Ordner, Regeln, Posteingang
- `text_analysis.py`, `topic_clusters.py` – Hashtags, Schlüsselwörter, Themencluster
- `web/index.html` – Web-App
- `instagram_links.py` – ältere Tkinter-Desktopversion (`python instagram_links.py`, benötigt Tkinter)

## Tests

```bash
python -m unittest discover -s tests -v
```

Nur Standardbibliothek, ausschließlich synthetische Testdaten. CI (GitHub Actions) läuft derzeit mit Python 3.12 auf Ubuntu.
