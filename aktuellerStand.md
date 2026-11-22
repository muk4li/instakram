# Aktueller Stand von instakram

**Dokumentationsabgleich 2026-11-22 · Codebasis:** `main` [`fddb7e9`](https://github.com/muk4li/instakram/commit/fddb7e9ca1b2f5a7da2efa10d09922d1ee21c63b). Local-first Python-/SQLite-App; kein authentik-/VPS-Deployment. Frühere lokale Prüfbelege und Produktgrenzen stehen im historischen Snapshot unten; keine neuen Code-/Live-Tests in diesem Doku-Abgleich. Centrality ADR-011 ist als Feedback-Backlog `IK-FB1` notiert, abhängig vom noch nicht freigegebenen öffentlichen feetbackhurts-Ingest. Keine UI-Implementierung.

## Historischer Snapshot

**Stand:** 2026-11-14 · **Basis-Commit:** `16701e3` auf `main`

- **Läuft:** Lokaler Import von Instagram-Exporten (ZIP bis 800 MB, JSON bis 150 MB) in SQLite,
  Web-UI auf 127.0.0.1:8765 mit Ordnern, Regeln, Posteingang, Hashtag-/Wort-Navigation und
  Themenclustern, Kodierungskorrektur. Erster Import des echten Nutzer-Exports (524 MB) erfolgt;
  Ergebnis: Hashtags leer, wenige Cluster – Ursachen in META-001/META-002.
- **Offen:** META-001/META-002 in Review (PR #5), UI-001 (Entwurf vom Nutzer),
  PERF-001, Entscheidungen SET-001/LEG-001; CI-001, SRV-001.
- **Nächster Schritt:** PR #5 mergen und Export neu importieren, Ergebnis prüfen.
