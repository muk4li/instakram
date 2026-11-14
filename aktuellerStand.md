# Aktueller Stand von instakram

**Stand:** 2026-11-14 · **Basis-Commit:** `16701e3` auf `main`

- **Läuft:** Lokaler Import von Instagram-Exporten (ZIP bis 800 MB, JSON bis 150 MB) in SQLite,
  Web-UI auf 127.0.0.1:8765 mit Ordnern, Regeln, Posteingang, Hashtag-/Wort-Navigation und
  Themenclustern, Kodierungskorrektur. Erster Import des echten Nutzer-Exports (524 MB) erfolgt;
  Ergebnis: Hashtags leer, wenige Cluster – Ursachen in META-001/META-002.
- **Offen:** META-001/META-002 in Review (PR #5), UI-001 (Entwurf vom Nutzer),
  PERF-001, Entscheidungen SET-001/LEG-001; CI-001, SRV-001.
- **Nächster Schritt:** PR #5 mergen und Export neu importieren, Ergebnis prüfen.
