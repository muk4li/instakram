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

## IMP-002 – Importlimit auf 800 MB erhöhen
- Status: In Review. Nutzer-Export ist 550 MB. Limit in Parser und Web-UI,
  Konsistenztest; synthetischer 600-MB-Upload über HTTP lokal geprüft.
