# Rückverfolgbarkeits-Tool (Miltenyi-Stil)

Webanwendung mit Datenbankanbindung (`DbConnector`), Eingabemasken für
Baugruppen (Gesamtgerät, Mikroskop) und einem Dashboard, das alle
gespeicherten Daten aus der Datenbank ausliest.

## Start

```bash
pip install flask
cd traceability_app
python app.py
```

Dann im Browser: <http://localhost:5000>

- **Dateneingabe**: Baugruppe wählen, Seriennummer + Komponenten
  (SAP-Nr., Rev., Order, SN, Datum) eintragen → „In Datenbank speichern".
- **Dashboard**: Kennzahlen, Suche und aufklappbare Geräteliste mit allen
  Komponenten.

## Datenbank

Standard: SQLite-Datei `traceability.db` neben der App. Über die
Umgebungsvariable `TRACE_DB_PATH` konfigurierbar. Alle DB-Zugriffe laufen
über `db_connector.DbConnector`, sodass ein späterer Wechsel auf einen
anderen Datenbankserver nur dort angepasst werden muss.

Die Komponentenlisten stammen aus der Excel/PDF
„Datenauflistung Rückverfolgbarkeit" und lassen sich in `app.py`
(`DEVICE_TEMPLATES`) erweitern.
