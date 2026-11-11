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


## Ordner & Gruppen (v3)

Die Bibliothek verwendet **SQLite** und speichert Links, selbst erstellte Ordner, Unterordner, Regeln und manuelle Zuordnungen dauerhaft unter `data/instakram.sqlite3`. Du kannst jeden Link **mehreren Gruppen** zuordnen. Standardmäßig sind die gewünschten Kategorien unter `groups/` vorhanden:

Tech & KI, Programmieren, Gaming, Memes & Humor, Musik, Wissen & Bildung, Favoriten, Fitness & Sport, Design & Kunst, Lifestyle, Inspiration, Rezepte, Anime, Filme und Serien.

In der Web-App kannst du Ordner auswählen, neue Ordner unter einem anderen Ordner anlegen, umbenennen, löschen und bei einem Link auf **Gruppen** klicken. Regeln wählen eine Gruppe und ein Feld wie URL, Absender, Chat, Typ oder Quelle und ordnen passende Links (auch bereits vorhandene) zu. Beim Entfernen einer Regel bleiben vorhandene Zuordnungen bestehen.

**Vorschläge:** „Stichwort-Vorschläge“ durchsucht lokal verfügbare Link-Metadaten nach bekannten Stichwörtern. Die optionale **lokale KI** nutzt [Ollama](https://ollama.com/) mit einem zuvor auf deinem Rechner installierten Modell (Standard: `llama3.2`). Beispiel:

```bash
ollama pull llama3.2
ollama serve
```

Ollama muss auf `127.0.0.1:11434` erreichbar sein. Erst nach Klick und Einwilligung werden **maximal 20 gefilterte Links** (URL und Metadaten) an Ollama auf deinem Computer geschickt; die KI erstellt lediglich **prüfbare Vorschläge**, keine automatische Übernahme. Ohne Reel-Inhalt ist die Erkennung zwangsläufig unvollständig. Lokale Stichwort-Vorschläge funktionieren ohne Ollama.

**Datenschutz:** Die SQLite-Datei enthält persönliche Links und Metadaten. Nicht ins Repository pushen. Für einen anderen Speicherort kannst du die Umgebungsvariable `INSTAKRAM_DB` setzen. Erstelle regelmäßig eine private Sicherung der SQLite-Datei.

**Migration:** Der erste Start legt die SQLite-Datei automatisch an. Ältere Exporte müssen einmalig erneut importiert werden. Importierte Links werden über ihre URL wiedererkannt; bestehende Ordner-Zuordnungen bleiben beim erneuten Import erhalten.


## Intelligenter Posteingang (v4)

- Neue oder noch nicht geprüfte Links erscheinen unter **Posteingang**. Dort auf **Prüfen** klicken, in der Ordnerliste einen oder mehrere Ordner auswählen und mit **Zuordnung bestätigen** abschließen. **Später prüfen** blendet den Link aus dem Posteingang aus; das wird nicht als negative Trainingsentscheidung behandelt.
- **Erneut prüfen** setzt eine bereits bestätigte Entscheidung zurück.
- Jede bestätigte Auswahl wird **nur lokal** als Feedback gespeichert. Das System merkt sich bestätigte und abgelehnte Kategorien.
- **Lernvorschläge:** Für wiedererkennbare Instagram-Profilnamen in der URL und spezifische externe Domains entstehen nach mindestens zwei gleichartigen, positiven Bestätigungen Vorschläge. Nach mindestens vier bestätigten Beispielen und ohne Gegenbeispiel können Links automatisch einer Gruppe zugeordnet werden, wenn die Automatik eingeschaltet und die Schwelle auf 95 steht.
- Die Bewertung **80/95 ist ein heuristischer Signalwert, keine statistisch kalibrierte Wahrscheinlichkeit**. Das System analysiert weder automatisch Videos noch erkennt es Creator aus Reel-IDs oder den Absendern eines Chats.
- In den Posteingang-Einstellungen kannst du die automatische Gruppenzuordnung deaktivieren oder die Schwelle verändern. Automatisch zugeordnete Links bleiben vorerst zur Sichtprüfung im Posteingang, bis du sie bestätigst.
- **Eigene Regeln** aus v3 bleiben aktiv und können unabhängig davon sofort zuordnen. Die vorhandene optionale Ollama-Funktion erzeugt weiterhin Vorschläge, keine automatische Videoanalyse.

**Technik:** SQLite-Tabellen `reviews`, `feedback`, `preferences`; neue APIs `/api/inbox/review`, `/api/inbox/undo`, `/api/inbox/settings`. Die Datenbank aktualisiert sich beim Start ohne manuelle Migration. Zur Sicherheit vorher eine Kopie von `data/instakram.sqlite3` erstellen.

**Qualität:** Weitere Unit-Tests für den Posteingang, erneute Importe, Lernen und Fehlzuordnungen sind unter `tests/` angelegt. Noch nicht mit echten umfangreichen Instagram-Exportdaten vollständig validiert.


## Hashtag- und Stichwort-Navigation (v5)

Die Weboberfläche hat links **Hashtags & Wörter**. Dort siehst du eine nach Häufigkeit geordnete Liste aller Hashtags und einfacher Schlüsselwörter, die **tatsächlich in den importierten JSON-Beschreibungen** gefunden wurden. Ein Klick auf einen Begriff zeigt die zugehörigen Links. Auch auf den Kacheln sind vorhandene Beschreibungstexte und Hashtags direkt sichtbar und anklickbar.

**Zählweise:** Ein Begriff wird pro **eindeutigem Link/URL nur einmal** gezählt, auch wenn der Link mehrmals geteilt oder importiert wurde und auch wenn derselbe Hashtag mehrfach in der Beschreibung steht. Groß-/Kleinschreibung wird vereinheitlicht (z. B. `#Anime` und `#anime`).

**Datenquellen:** Die Erkennung berücksichtigt explizite Felder `caption`, `description`, `alt_text` oder `accessibility_caption`, soweit sie im Export vorhanden und einem Link zuordenbar sind. Eine Chat-Nachricht mit einem Reel-Link ist **nicht automatisch die Beschreibung des Reels**. Die App lädt keine fremden Instagram-Beschreibungen aus dem Netz und kann fehlende Caption-Daten nicht rekonstruieren.

**Schlüsselwörter:** Eine einfache lokale Worthäufigkeits-Heuristik mit deutscher/englischer Stoppwortliste; **keine KI**, keine semantische Analyse. Dadurch können unpassende Stichwörter vorkommen. Die Zählung erfolgt auf eindeutigen URLs, nicht auf Wörtern pro Satz.

**Migration:** Vorhandene SQLite-Daten bleiben erhalten; neue Tabellen werden automatisch angelegt. Damit bereits importierte Links neue Beschreibungen erhalten, musst du den JSON/ZIP-Export **einmal erneut importieren**.

**Automatische Sortierregeln:** Im Regel-Editor gibt es jetzt das Feld **„Beschreibung/Hashtag enthält“**. Beispiel: Wenn eine tatsächlich exportierte Beschreibung `#anime` enthält, den Link nach `groups/Anime` zuordnen. Regeln funktionieren auch für bereits importierte Links; sie können fehlende Beschreibungen nicht ersetzen.
