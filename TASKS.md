# Operatives Backlog

## ENC-001 – Mojibake aus Instagram-Exporten reparieren
- Status: Abgeschlossen (PR #1, gemergt als `663191d`, CI grün). Parser repariert UTF-8-als-Latin-1-Text; bestehende
  Datenbanken werden einmalig beim Start ohne Duplikate repariert.

## SET-001 – Standardwert der automatischen Gruppenzuordnung prüfen
- Status: Offen – **Entscheidung beim Nutzer.**
- Derzeit `auto_enabled='1'` (automatische Zuordnung ab Signal 95 aktiv).
  Zu klären, ob neue Datenbanken mit deaktivierter Automatik starten sollen.

## LEG-001 – Legacy-Tkinter-Skript `instagram_links.py`
- Status: Offen – **Entscheidung beim Nutzer:** entfernen oder bewusst behalten.

## CI-001 – CI-Matrix erweitern
- Status: Offen. Python 3.10/3.11/3.13 × ubuntu-latest/windows-latest
  (derzeit nur Python 3.12 auf ubuntu).

## SRV-001 – Port in Host-Prüfung aus Konstante ableiten
- Status: Offen. `server.py` prüft `Host`/`Origin` gegen fest eingetragenes
  `8765` statt gegen `PORT`.

## E2E-001 – End-to-End-Test mit echtem Export
- Status: Offen. Nur lokal durch den Nutzer; Daten und Ergebnisse nicht
  committen, nur anonymisierte Befunde zurückmelden.

## IMP-002 – Importlimits erhöhen
- Status: Abgeschlossen (PR #4). ZIP 200 → 800 MB (Nutzer-Export 524 MB),
  JSON-Einzeldatei 80 → 150 MB (Likes-Datei des Nutzers 88,9 MB).
  Likes sowie Follower/Werbung/Login werden bewusst mitimportiert (Nutzerentscheidung).

## PERF-001 – API für große Bibliotheken
- Status: Offen, zusammen mit der neuen UI planen.
- `/api/library` und jede POST-Antwort liefern alle Links (`all_links()`, mehrere
  Abfragen pro Link). Synthetisch gemessen: 100 000 Links 2 s / 55 MB,
  500 000 Links 11 s / 275 MB je Aktion. Nötig: Paginierung/Filter serverseitig,
  POST-Antworten nur mit geänderten Daten.

## META-001 – Export-Metadaten auswerten (Chats)
- Status: In Review. `share_text` (Caption) und `original_content_owner` (Creator) geteilter
  Beiträge, Chat-/Gruppenname und Teilnehmerzahl, Reaktionen, Quelltyp aus dem Pfad,
  Relevanzsignale; Lernen nach exportiertem Creator. Behebt außerdem, dass die
  Hashtag-Ansicht nach Import/Neuladen leer blieb. Erfordert einmaligen Reimport.

## META-002 – Gespeichert/Likes im `label_values`-Format
- Status: In Review (zusammen mit META-001). Struktur aus maskierter Probe des Nutzers:
  oberste `URL` = Beitrag, `Untertitel` = Caption, `Benutzername` im Eigentümer-Block = Creator.
  Die URL im Eigentümer-Block (z. B. Website) wird nicht mehr als eigener Link importiert.
  Älteres Format (`title` + `string_map_data`/`string_list_data`) für Gespeichert/Likes ebenfalls.

## UI-001 – Oberfläche überarbeiten
- Status: Teilweise umgesetzt: Import auf eigener Seite, „Kopieren“ entfernt,
  Chat-Übersicht. Offen: Quellen-Navigation, Sortierung nach Relevanz,
  „Gruppen“-Zuordnung direkt am Link, Markierung „nicht mehr verfügbar“.
