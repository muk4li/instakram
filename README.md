# instakram ✦

Eine **lokale Instagram-Link-Bibliothek** mit moderner Browseroberfläche. Sammle URLs aus einem privaten Chat, aus gespeicherten Reels/Posts und aus deinen Archivdaten – **ohne Instagram-Anmeldung**.

## 🚀 Schnellstart (v2)

Du benötigst nur **Python 3**. Keine zusätzlichen Pakete erforderlich.

1. Repository herunterladen oder klonen.
2. Im Repository-Ordner einen Terminal öffnen.
3. Starten:

   ```bash
   python server.py
   ```

   Unter macOS/Linux gegebenenfalls `python3 server.py` verwenden.
4. Der Browser öffnet **http://127.0.0.1:8765**. Andernfalls diese Adresse manuell öffnen.
5. Deinen offiziellen **Instagram-Datenexport als ZIP oder JSON** per Drag-and-drop hineinziehen.

**Hinweis:** Die bisherige Desktop-Version steht weiterhin über `python instagram_links.py` zur Verfügung (benötigt Tkinter).

## Funktionen

- Schöne responsive UI mit Kacheln und Listenansicht
- Suche nach Links, Chat, Absender und Dateiname
- Filter: Chat, gespeicherte Inhalte, Archiv, Inhaltstyp
- Instagram-Reels, Posts und andere URLs erkennen
- Excel-kompatiblen CSV-Export erstellen
- **Optionale Instagram-Einbettungen:** Nur nach ausdrücklicher Zustimmung lädt die App Instagrams offizielles Embed-Skript. Öffentliche Reels und Posts *können* als Vorschau angezeigt werden. Jeder Eintrag hat stets einen „Öffnen“-Link.

## Datenexport vorbereiten

Instagram → Kontenübersicht → Deine Informationen und Berechtigungen → Informationen exportieren. **JSON**, gesamter Zeitraum und gewünschte Kategorien auswählen. ZIP auf deinem Rechner speichern und in instakram importieren.

## Datenschutz

- ZIP und JSON werden an einen **lokalen Python-Prozess** auf **127.0.0.1** gesendet, dort im Speicher verarbeitet und **nicht dauerhaft gespeichert**.
- Keine Anmeldung, keine Tokens, keine Cloud-API.
- Erst nach aktivem Einverständnis können für Embeds Netzwerkverbindungen zu **instagram.com** entstehen. Dabei können Browser-/Netzwerkdaten an Meta gehen.
- Stelle **niemals** deine exportierten Chats, ZIP-Dateien oder CSV-Dateien in ein öffentliches GitHub-Repository.

## Grenzen

- Instagram liefert nicht immer URLs für geteilte Reels. Nur tatsächlich enthaltene Links werden erfasst.
- Archivierte Medien haben nicht unbedingt einen eigenen öffentlichen Link.
- Instagram-Embeds funktionieren grundsätzlich nur für **öffentliche, aktive und dafür freigegebene Posts/Reels**. Private, gelöschte, eingeschränkte Posts und Stories lassen sich nicht einbetten.
- Die App kann nichts auf Instagram löschen, entspeichern oder verändern.
- Die Zuordnung zu Archiv/gespeichert richtet sich nach Dateipfaden des Exports und kann unvollständig sein.
- Vorschau ist auf 80 Kacheln bzw. 500 Zeilen begrenzt; die CSV enthält alle gefilterten Treffer.
- Importlimit: 200 MB je Datei (JSON-Einzeldateien max. 80 MB).

## Projektstruktur

- `server.py` – lokaler HTTP-Server
- `parser_core.py` – ZIP/JSON-Parser
- `web/index.html` – Web-App
- `instagram_links.py` – ältere Tkinter-Version

**Status:** v2 Beta. Noch nicht an einem realen großen Instagram-Export end-to-end getestet.
