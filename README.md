# ☀️ PV Anlagen Dimensionierung

Web-App zur Dimensionierung von Photovoltaik-Anlagen basierend auf echten Solardaten.

## Features
- Standort-basierte Solardaten via **PVGIS API** (EU Joint Research Centre)
- Automatischer Vergleich von **5 Ausrichtungsszenarien** (Süd, Ost, West, ...)
- Berechnung von **kWp, Modulanzahl, Jahresertrag, Performance Ratio**
- Wirtschaftlichkeitsrechnung: Amortisation, CO₂-Einsparung
- Verlustaufschlüsselung (Temperatur, Kabel, Wechselrichter, Shading)
- Monatliches Ertragsprofil (echte PVGIS-Monatsdaten)
- JSON-Export der Ergebnisse
- Optimiert für iPhone / Mobile

## Tech Stack
- Python 3.12
- Streamlit
- PVGIS 5.3 API (kostenlos, keine Registrierung)

## Lokale Entwicklung
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Datenquelle
PVGIS 5.3 · EU Joint Research Centre  
https://re.jrc.ec.europa.eu · Kostenlos & Open Access
