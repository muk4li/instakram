# Aktueller Stand von instakram

**Stand:** 2026-11-14 · **Basis-Commit:** `f0a9d60` auf `main`

- **Läuft:** Lokaler Import von Instagram-Exporten (ZIP/JSON) in SQLite, Web-UI auf
  127.0.0.1:8765 mit Ordnern, Regeln, Posteingang, Hashtag-/Wort-Navigation und
  Themenclustern, Kodierungskorrektur für Instagram-Mojibake (PR #1). 32 Unit-Tests lokal grün (Python 3.13, Linux), CI nur Python 3.12/ubuntu.
- **Offen:** Entscheidungen SET-001 und LEG-001 beim Nutzer; CI-001, SRV-001, E2E-001 in `TASKS.md`. Noch kein Test mit echtem Export.
- **Nächster Schritt:** E2E-001 lokal durch den Nutzer, danach CI-001.
