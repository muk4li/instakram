# Verbindlicher Entwicklungsablauf

- Vor Änderungen `git status` und `git fetch origin main` ausführen, den
  Ausgangscommit festhalten und bestehende Nutzeränderungen erhalten. Vorhandenen
  Code und Tests lesen, bevor neue Mechanismen gebaut werden.
- Auf einem Feature-Branch in kleinen, vollständigen Arbeitspaketen arbeiten.
  PR gegen main; kein Force-Push, Merge nur bei grüner CI.
- Ausschließlich synthetische Testdaten. Echte Instagram-Exporte, ZIP/JSON/CSV,
  SQLite-Datenbanken, private Namen/IDs und Secrets niemals committen. Vor jedem
  Commit gestagte Dateiliste und Inhalte prüfen.
- Local-first: Server nur an Loopback (127.0.0.1) binden, keine Cloud-Dienste
  für Exportinhalte, Instagram-Embeds nur nach ausdrücklicher Zustimmung.
- Keine neuen Pflichtabhängigkeiten; Laufzeit bleibt Python-Standardbibliothek.
- Bestehende Datenbanken transaktional und ohne Datenverlust migrieren;
  Ordner-Zuordnungen, Reviews und Feedback erhalten.
- Vor jedem Commit `python -m unittest discover -s tests -v` ausführen und für
  wesentliche Änderungen Regressionstests ergänzen.
- Nichts als fertig, getestet oder plattformkompatibel behaupten, was nicht
  tatsächlich verifiziert ist. Blockierte Schritte offen benennen.
- Nach abgeschlossenen Schritten README, `aktuellerStand.md` und `TASKS.md`
  aktualisieren. Bericht: Ausgangscommit, Änderung, Tests, PR/CI, offene Punkte.

# Übergreifende Architektur

- [Centrality](https://github.com/muk4li/centrality) besitzt die Gesamtarchitektur
  und die Verträge zwischen den Repositories. Bei repoübergreifenden Änderungen
  (z. B. Hub-Anbindung, Auth, Netzwerkbindung, Packaging) zuerst dort
  `docs/START-HERE.md`, `DECISIONS.md` und `CURRENT-STATE.md` lesen. Für instakram
  selbst bleiben Code, Tests und diese Datei maßgeblich.
- Ist Centrality nicht erreichbar, die Lücke melden und keine grenzverändernden
  Entscheidungen treffen. Keine privaten Centrality-Inhalte hierher kopieren.
