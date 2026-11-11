# instakram — Instagram-Link-Sammler

Eine lokale Desktop-App zum Sammeln von Links aus dem offiziellen Instagram-Datenexport.

## Funktionen
- Instagram-Datenexport als **ZIP** oder einzelne **JSON-Datei** öffnen
- URLs in Nachrichten, gespeicherten Inhalten und Archivdaten erkennen (soweit im Export vorhanden)
- Links nach Bereich und privatem Chat filtern
- Reels, Posts, Stories und andere Links unterscheiden
- Duplikate je Bereich und Chat entfernen
- Gefilterte Ergebnisse als **Excel-kompatible CSV** speichern

## Installation / Start

Voraussetzung: **Python 3** mit **Tkinter** (unter Windows und macOS bei vielen Python-Installationen enthalten, auf Linux ggf. `python3-tk` nachinstallieren).

Repository herunterladen oder klonen und im Ordner starten:

```bash
python instagram_links.py
```

Unter einigen Linux-/macOS-Systemen stattdessen `python3 instagram_links.py` verwenden.

Keine zusätzlichen Python-Pakete notwendig.

## Instagram-Export anfordern

In Instagram bzw. der Meta-Kontenübersicht **Deine Informationen und Berechtigungen → Deine Informationen exportieren** aufrufen, Instagram wählen und **JSON** sowie **gesamter Zeitraum** auswählen. Wenn der Export verfügbar ist, die ZIP-Datei herunterladen und im Tool öffnen.

## Datenschutz
- Kein Instagram-Login erforderlich
- Verarbeitung ausschließlich lokal und offline
- Es werden keine Daten an Server geschickt
- **Keine privaten Chat-Exporte oder exportierten CSV-Dateien ins öffentliche GitHub-Repository committen!**

## Grenzen von v1

Instagram exportiert geteilte Reels/Posts nicht immer als vollständige URLs. Die App kann **nur die tatsächlich vorhandenen Links** extrahieren und fehlende Links nicht rekonstruieren. Die Zuordnung zu „Archiv“ und „Gespeichert“ erfolgt über Export-Dateipfade und ist je nach Exportstruktur möglicherweise unvollständig. Archivierte Medien müssen nicht zwangsläufig öffentliche Links haben.

Die App verändert **keine** Daten auf Instagram und lädt keine Reels herunter.

## Status
Erste Version; mit Beispieldaten getestet, noch nicht mit einem echten Instagram-Gesamtexport umfassend validiert.
