# Aktueller Stand von instakram

**Stand:** 2026-11-14 · **Basis-Commit:** `4495cb8` auf `main` (zzgl. offenem PR #1)

- **Läuft:** Lokaler Import von Instagram-Exporten (ZIP/JSON) in SQLite, Web-UI auf
  127.0.0.1:8765 mit Ordnern, Regeln, Posteingang, Hashtag-/Wort-Navigation und
  Themenclustern. 32 Unit-Tests lokal grün (Python 3.13, Linux), CI nur Python 3.12/ubuntu.
- **Offen:** PR #1 (Kodierungskorrektur) in Review; Entscheidungen SET-001 und LEG-001
  beim Nutzer; CI-001, SRV-001, E2E-001 in `TASKS.md`. Noch kein Test mit echtem Export.
- **Nächster Schritt:** PR #1 mergen, danach E2E-001 lokal durch den Nutzer.
