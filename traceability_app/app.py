"""Rückverfolgbarkeits-Tool im Miltenyi-Stil.

Eingabemasken für Baugruppen (Gesamtgerät, Mikroskop, ...) mit
Komponentenliste (SAP-Nr., Rev., Order, SN, Datum). Beim Speichern
werden die Daten über den DbConnector in die Datenbank gepusht;
das Dashboard liest alle Datensätze wieder aus.

Start:  python app.py   →  http://localhost:5000
"""

from flask import Flask, render_template, request, redirect, url_for, flash

from db_connector import DbConnector

app = Flask(__name__)
app.secret_key = "traceability-tool"
db = DbConnector()

# Vorbelegte Baugruppen-Templates (aus "Datenauflistung Rückverfolgbarkeit")
DEVICE_TEMPLATES = {
    "Gesamtgerät": [
        "Grundrahmen", "Power Supply", "Light Box", "CPC", "Chassis",
        "Multi Color Light Unit", "Mikroskop", "Y-Frame", "Y-Spindel",
        "X-Spindel", "Needle Arm Unit", "SRC", "CPU", "Monitor",
        "Dillutor", "Quattro", "Fluidik Schlauch Set",
        "Verkleidung mit Tür", "Tür",
    ],
    "Mikroskop": [
        "Filterwechsler", "Dichroic Schnellwechsler", "Kameraeinheit MACSima",
        "Z-Achsen Lineartisch", "Objektivschiebereinheit", "Auto-Fokus-MACSima",
        "MACSima Illumination",
    ],
}


@app.route("/")
def index():
    return redirect(url_for("entry"))


@app.route("/entry", methods=["GET", "POST"])
def entry():
    device_type = request.values.get("device_type", "Gesamtgerät")
    if device_type not in DEVICE_TEMPLATES:
        device_type = "Gesamtgerät"

    if request.method == "POST":
        serial = request.form.get("serial_number", "").strip()
        if not serial:
            flash("Bitte eine Seriennummer eingeben.", "error")
        else:
            names = request.form.getlist("comp_name")
            components = [
                {
                    "name": names[i],
                    "sap_nr": request.form.getlist("comp_sap")[i],
                    "rev": request.form.getlist("comp_rev")[i],
                    "order_nr": request.form.getlist("comp_order")[i],
                    "sn": request.form.getlist("comp_sn")[i],
                    "comp_date": request.form.getlist("comp_date")[i],
                }
                for i in range(len(names))
            ]
            db.save_device(device_type, serial, components)
            flash(f"{device_type} {serial} wurde gespeichert.", "success")
            return redirect(url_for("dashboard"))

    return render_template(
        "entry.html",
        device_type=device_type,
        device_types=list(DEVICE_TEMPLATES),
        components=DEVICE_TEMPLATES[device_type],
    )


@app.route("/dashboard")
def dashboard():
    search = request.args.get("q", "").strip()
    return render_template(
        "dashboard.html",
        devices=db.fetch_devices(search or None),
        stats=db.stats(),
        search=search,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
