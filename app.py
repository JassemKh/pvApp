import streamlit as st
import requests
import math
import json
import pandas as pd

# ── Seitenkonfiguration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="☀️ PV Dimensionierung",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Mobile-optimiertes Styling ───────────────────────────────────────────────
st.markdown("""
<style>
    /* Mobile-first Layout */
    .main .block-container { padding: 0.8rem 1rem 2rem 1rem; max-width: 900px; }
    section[data-testid="stSidebar"] { display: none; }

    /* KPI Kacheln */
    .kpi-box {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 0.9rem 0.5rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: #e65c00; line-height: 1.1; }
    .kpi-label { font-size: 0.72rem; color: #666; margin-top: 4px; line-height: 1.2; }
    .kpi-unit  { font-size: 0.85rem; font-weight: 400; color: #e65c00; }

    /* Szenarien */
    .sz-card {
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.4rem;
    }
    .sz-best { border: 2px solid #e65c00; background: #fff8f3; }
    .sz-bar-bg { background: #eee; border-radius: 5px; height: 7px; margin-top: 5px; }
    .sz-bar    { background: #e65c00; height: 7px; border-radius: 5px; }

    /* Verlust-Tabelle */
    .v-row {
        display: flex; justify-content: space-between;
        padding: 4px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.85rem;
    }

    /* Empfehlung */
    .empfehlung {
        background: #e8f5e9; border-left: 4px solid #4caf50;
        border-radius: 0 10px 10px 0; padding: 1rem; margin: 1rem 0;
    }

    /* Button */
    .stButton > button {
        background: #e65c00 !important; color: white !important;
        border: none !important; border-radius: 10px !important;
        padding: 0.65rem 1.5rem !important; font-size: 1rem !important;
        width: 100% !important;
    }
    .stButton > button:hover { background: #cc5000 !important; }

    /* Headings */
    h1 { font-size: 1.4rem !important; margin-bottom: 0.3rem !important; }
    h2 { font-size: 1.1rem !important; margin-top: 1rem !important; }
    h3 { font-size: 1rem !important; }
    p.caption { font-size: 0.78rem; color: #888; }
</style>
""", unsafe_allow_html=True)

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def pvgis_abrufen(lat: float, lon: float, neigung: int, azimut: int, verlust: float):
    """PVGIS API — Ergebnis wird 1h gecacht um API zu schonen."""
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    params = {
        "lat": round(lat, 4), "lon": round(lon, 4),
        "peakpower": 1, "loss": round(verlust, 1),
        "angle": neigung, "aspect": azimut,
        "outputformat": "json", "pvtechchoice": "crystSi",
        "mountingplace": "free",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        ertrag    = data["outputs"]["totals"]["fixed"]["E_y"]
        monatlich = [round(m["E_m"]) for m in data["outputs"]["monthly"]["fixed"]]
        return round(ertrag, 1), monatlich
    except Exception:
        return None, None

def verlust_gesamt(temp, kabel, wr, schmutz):
    eta = (1-temp/100) * (1-kabel/100) * (1-wr/100) * (1-schmutz/100)
    return round((1-eta)*100, 1)

def opt_neigung(lat):
    return max(10, round(lat * 0.76))

def kpis_berechnen(jahresbedarf, ertrag_kwp, fläche_m2, modul_wp, ev_anteil):
    modul_fläche = 1.72
    max_module   = math.floor(fläche_m2 / modul_fläche)
    max_kwp      = max_module * modul_wp / 1000
    nötig_kwp    = jahresbedarf / ertrag_kwp
    emp_kwp      = round(min(nötig_kwp, max_kwp), 2)
    module       = math.ceil(emp_kwp * 1000 / modul_wp)
    ertrag_j     = round(emp_kwp * ertrag_kwp)
    fläche_nötig = round(module * modul_fläche, 1)
    pr           = min(95, round(ertrag_kwp / (1200 * 0.87) * 100, 1))
    ev_kwh       = round(ertrag_j * ev_anteil / 100)
    einsp_kwh    = ertrag_j - ev_kwh
    einsparung   = ev_kwh * 0.30 + einsp_kwh * 0.082
    invest       = round(emp_kwp * 1200)
    amort        = round(invest / einsparung, 1) if einsparung > 0 else 99
    co2          = round(ertrag_j * 0.385 / 1000, 1)
    deckung      = min(100, round(ertrag_j / jahresbedarf * 100))
    return {
        "emp_kwp": emp_kwp, "module": module, "ertrag_j": ertrag_j,
        "fläche_nötig": fläche_nötig, "max_kwp": round(max_kwp, 2),
        "fläche_ok": fläche_m2 >= fläche_nötig, "pr": pr,
        "ev_kwh": ev_kwh, "einsp_kwh": einsp_kwh,
        "invest": invest, "amort": amort, "co2": co2, "deckung": deckung,
        "einsparung_j": round(einsparung),
    }

# ── Szenarien-Definition ─────────────────────────────────────────────────────
SZENARIEN = [
    {"name": "Süd optimal",  "azimut":   0, "icon": "S"},
    {"name": "Süd-Ost",      "azimut": -45, "icon": "SO"},
    {"name": "Süd-West",     "azimut":  45, "icon": "SW"},
    {"name": "Ost",          "azimut": -90, "icon": "O"},
    {"name": "West",         "azimut":  90, "icon": "W"},
]

# ── App ──────────────────────────────────────────────────────────────────────
st.title("☀️ PV Anlagen Dimensionierung")
st.markdown('<p class="caption">Solardaten: PVGIS 5.3 · EU Joint Research Centre · kostenlos & frei</p>',
            unsafe_allow_html=True)

# ══ EINGABEN ════════════════════════════════════════════════════════════════

with st.expander("📍 Standort", expanded=True):
    STÄDTE = {
        "Manuell eingeben": None,
        "München (48.14, 11.58)": (48.14, 11.58),
        "Berlin (52.52, 13.40)":  (52.52, 13.40),
        "Hamburg (53.55, 9.99)":  (53.55, 9.99),
        "Frankfurt (50.11, 8.68)":(50.11,  8.68),
        "Stuttgart (48.78, 9.18)":(48.78,  9.18),
        "Köln (50.93, 6.96)":     (50.93,  6.96),
        "Wien (48.21, 16.37)":    (48.21, 16.37),
        "Zürich (47.38, 8.54)":   (47.38,  8.54),
        "Tunis (36.82, 10.17)":   (36.82, 10.17),
        "Dubai (25.20, 55.27)":   (25.20, 55.27),
        "Madrid (40.42, -3.70)":  (40.42, -3.70),
        "Rom (41.90, 12.50)":     (41.90, 12.50),
    }
    stadt = st.selectbox("Stadt wählen:", list(STÄDTE.keys()))
    if STÄDTE[stadt]:
        lat_default, lon_default = STÄDTE[stadt]
    else:
        lat_default, lon_default = 48.14, 11.58

    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Breitengrad", min_value=27.0, max_value=72.0,
                              value=lat_default, step=0.01,
                              help="Google Maps: langer Tap auf Standort → Koordinaten kopieren")
    with col2:
        lon = st.number_input("Längengrad", min_value=-30.0, max_value=55.0,
                              value=lon_default, step=0.01)

with st.expander("🏠 Dach & Module", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        fläche = st.number_input("Verfügbare Dachfläche (m²)", min_value=5.0,
                                  max_value=1000.0, value=30.0, step=1.0)
        modul_wp = st.selectbox("Modul-Leistung", [380, 400, 420, 450, 500, 550],
                                 index=2, format_func=lambda x: f"{x} Wp")
    with col2:
        ausrichtung = st.radio("Ausrichtung:", ["Automatisch (alle Szenarien)",
                                                 "Manuell wählen"])
        if ausrichtung == "Manuell wählen":
            az_wahl = st.selectbox("Himmelsrichtung:",
                                    ["Süd", "Süd-Ost", "Süd-West", "Ost", "West"])
            az_map = {"Süd": 0, "Süd-Ost": -45, "Süd-West": 45, "Ost": -90, "West": 90}
            man_az = az_map[az_wahl]
        neigung = st.slider("Dachneigung (°)", 0, 60, opt_neigung(lat),
                             help=f"Optimal für diesen Standort: ca. {opt_neigung(lat)}°")

with st.expander("⚡ Verbrauch & Verluste", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        bedarf = st.number_input("Jahresstromverbrauch (kWh/Jahr)", min_value=500,
                                  max_value=100000, value=4500, step=100)
        ev = st.slider("Eigenverbrauchsanteil (%)", 10, 80, 30,
                        help="Anteil des PV-Stroms der sofort selbst genutzt wird")
    with col2:
        st.caption("Verlustparameter:")
        vt = st.slider("Temperatur (%)",         0, 15,  7)
        vk = st.slider("Kabel (%)",              0,  5,  2)
        vw = st.slider("Wechselrichter (%)",      0,  8,  4)
        vs = st.slider("Verschmutzung/Shading (%)", 0, 20, 5)

vg = verlust_gesamt(vt, vk, vw, vs)
st.info(f"Gesamtverlust: **{vg}%** → Systemeffizienz: **{100-vg}%**")

# ══ BERECHNUNG ══════════════════════════════════════════════════════════════

st.markdown("---")
start = st.button("🔍 Jetzt dimensionieren", type="primary")

if start:
    auto = ausrichtung == "Automatisch (alle Szenarien)"

    with st.spinner("Lade Solardaten von PVGIS…"):
        if auto:
            ergebnisse = []
            for sz in SZENARIEN:
                e, mon = pvgis_abrufen(lat, lon, neigung, sz["azimut"], vg)
                if e:
                    ergebnisse.append({**sz, "ertrag": e, "monatlich": mon})
            if not ergebnisse:
                st.error("PVGIS nicht erreichbar — bitte Internetverbindung prüfen.")
                st.stop()
            bestes   = max(ergebnisse, key=lambda x: x["ertrag"])
            ertrag   = bestes["ertrag"]
            monatlich= bestes["monatlich"]
            az_name  = bestes["name"]
        else:
            ertrag, monatlich = pvgis_abrufen(lat, lon, neigung, man_az, vg)
            if not ertrag:
                st.error("PVGIS nicht erreichbar.")
                st.stop()
            ergebnisse = None
            az_name    = az_wahl

    k = kpis_berechnen(bedarf, ertrag, fläche, modul_wp, ev)

    # ── KPI-Kacheln ─────────────────────────────────────────────────────────
    st.success("✅ Berechnung abgeschlossen!")
    st.markdown("## 📊 Kernergebnisse")

    c1,c2,c3,c4 = st.columns(4)
    for col, val, unit, label in [
        (c1, k["emp_kwp"], "kWp",  "Anlagengröße"),
        (c2, f"{k['ertrag_j']:,}", "kWh/J", "Jahresertrag"),
        (c3, k["module"],  "Stk",  f"Module ({modul_wp}Wp)"),
        (c4, f"{k['pr']}", "%",    "Performance Ratio"),
    ]:
        with col:
            st.markdown(f"""<div class="kpi-box">
                <div class="kpi-value">{val}<span class="kpi-unit"> {unit}</span></div>
                <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    c5,c6,c7,c8 = st.columns(4)
    for col, val, unit, label in [
        (c5, k["amort"],  "Jahre", "Amortisation"),
        (c6, f"{k['einsparung_j']:,}", "€/J", "Einsparung+Vergütung"),
        (c7, f"{k['invest']:,}", "€", "Investition (ca.)"),
        (c8, k["co2"],    "t/J",  "CO₂-Einsparung"),
    ]:
        with col:
            st.markdown(f"""<div class="kpi-box">
                <div class="kpi-value">{val}<span class="kpi-unit"> {unit}</span></div>
                <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    # ── Szenarien-Vergleich ──────────────────────────────────────────────────
    if ergebnisse:
        st.markdown("## 🔄 Ausrichtungs-Vergleich")
        st.caption("Jahresertrag pro kWp — PVGIS-Echtwerte")
        max_e = max(s["ertrag"] for s in ergebnisse)
        for s in sorted(ergebnisse, key=lambda x: x["ertrag"], reverse=True):
            pct   = s["ertrag"] / max_e * 100
            best  = s["ertrag"] == max_e
            cls   = "sz-card sz-best" if best else "sz-card"
            badge = "  ★ BESTE" if best else ""
            st.markdown(f"""
            <div class="{cls}">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <b>{s['name']}{badge}</b>
                <span style="font-size:1.1rem;font-weight:700;color:#e65c00;">{s['ertrag']} kWh/kWp</span>
              </div>
              <div class="sz-bar-bg"><div class="sz-bar" style="width:{pct:.0f}%"></div></div>
              <div style="font-size:0.73rem;color:#999;margin-top:2px;">{pct:.0f}% vom Maximum</div>
            </div>""", unsafe_allow_html=True)

    # ── Monatsprofil ─────────────────────────────────────────────────────────
    st.markdown("## 📅 Monatsprofil")
    monate = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
    if monatlich and len(monatlich) == 12:
        faktor = k["emp_kwp"]
        werte  = [round(m * faktor) for m in monatlich]
    else:
        profil = [.035,.05,.08,.10,.12,.13,.13,.12,.10,.07,.04,.03]
        werte  = [round(k["ertrag_j"] * p) for p in profil]
    df = pd.DataFrame({"Ertrag (kWh)": werte}, index=monate)
    st.bar_chart(df, color="#e65c00", height=220)

    # ── Verlust-Detail & Flächencheck ────────────────────────────────────────
    st.markdown("## 📉 Details")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.caption("Verluste:")
        for n, v in [("Temperatur", vt),("Kabel", vk),("Wechselrichter", vw),("Verschmutzung/Shading", vs)]:
            st.markdown(f'<div class="v-row"><span>{n}</span><span style="color:#c04000;">−{v}%</span></div>',
                        unsafe_allow_html=True)
        st.markdown(f'<div class="v-row" style="font-weight:700;border:none;padding-top:6px;">'
                    f'<span>Gesamt</span><span style="color:#c04000;">−{vg}%</span></div>',
                    unsafe_allow_html=True)
    with col_d2:
        icon = "✅" if k["fläche_ok"] else "⚠️"
        st.markdown(f"""
        <div style="background:#f4f6f8;border-radius:10px;padding:0.9rem;font-size:0.88rem;">
            <b>Flächencheck</b><br><br>
            Verfügbar: <b>{fläche} m²</b><br>
            Benötigt: <b>{k['fläche_nötig']} m²</b><br>
            Max. möglich: <b>{k['max_kwp']} kWp</b><br><br>
            {icon} {'Fläche reicht aus' if k['fläche_ok'] else 'Fläche begrenzt die Anlage'}
        </div>""", unsafe_allow_html=True)

    # ── Empfehlung ───────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="empfehlung">
        <b>✅ Empfehlung für deinen Standort</b><br><br>
        Installiere <b>{k['emp_kwp']} kWp</b> ({k['module']} × {modul_wp} Wp)
        in <b>{az_name}</b>-Ausrichtung, {neigung}° Neigung.<br>
        Jahresertrag: <b>{k['ertrag_j']:,} kWh</b> · deckt <b>{k['deckung']}%</b> deines Bedarfs.<br>
        Amortisation nach ca. <b>{k['amort']} Jahren</b> ·
        CO₂-Einsparung: <b>{k['co2']} t/Jahr</b>.
    </div>""", unsafe_allow_html=True)

    # ── JSON Export ──────────────────────────────────────────────────────────
    export = {
        "Standort": {"lat": lat, "lon": lon, "Stadt": stadt},
        "Anlage": {"kWp": k["emp_kwp"], "Module": k["module"], "Wp": modul_wp,
                   "Neigung_Grad": neigung, "Ausrichtung": az_name},
        "Ertrag": {"Jahresertrag_kWh": k["ertrag_j"], "pro_kWp_kWh": ertrag, "PR_pct": k["pr"]},
        "Wirtschaft": {"Invest_EUR": k["invest"], "Einsparung_EUR_J": k["einsparung_j"],
                       "Amort_Jahre": k["amort"], "CO2_t_J": k["co2"]},
        "Verluste_pct": {"Temperatur": vt, "Kabel": vk, "WR": vw,
                         "Schmutz": vs, "Gesamt": vg},
    }
    st.download_button("📥 Ergebnisse als JSON", data=json.dumps(export, indent=2, ensure_ascii=False),
                       file_name="pv_ergebnis.json", mime="application/json")

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Daten: PVGIS 5.3 · EU JRC · Keine Finanzberatung · Schätzwerte")
