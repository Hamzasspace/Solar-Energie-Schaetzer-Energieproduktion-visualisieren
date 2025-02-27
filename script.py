import streamlit as st
from datetime import datetime, timedelta
import pytz
from timezonefinder import TimezoneFinder
from pysolar.solar import get_altitude
import ephem
import requests
import pandas as pd
import numpy as np
import plotly.express as px

# Titel der App (zentriert und größer)
st.markdown(
    "<h1 style='text-align: center; font-size: 40px;'>☀️ Solar-Energie-Schätzer</h1>",
    unsafe_allow_html=True
)

# Funktion zur Berechnung der Energieproduktion
def calculate_energy(location, start_date, end_date):
    # API-Schlüssel für OpenWeatherMap
    api_key = "b3a160e9fec8f37993c763aa1923c8f8"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
    response = requests.get(url).json()

    # Konstanten
    PANEL_EFFICIENCY = 0.18
    PANEL_AREA = 10
    SOLAR_CONSTANT = 1361
    TEMPERATURE_COEFFICIENT = -0.005

    if response.get("cod") == 200:
        lat = response["coord"]["lat"]
        lon = response["coord"]["lon"]
        clouds = response["clouds"]["all"]
        temp = response["main"]["temp"]

        # Zeitzone bestimmen
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=lat, lng=lon) or "UTC"
        timezone = pytz.timezone(timezone_str)

        # Lokale Zeiten setzen
        start_time = timezone.localize(datetime.combine(start_date, datetime.min.time()))
        end_time = timezone.localize(datetime.combine(end_date, datetime.max.time()))

        # Sonnenaufgang & -untergang
        sunrise = datetime.fromtimestamp(response["sys"]["sunrise"], tz=timezone)
        sunset = datetime.fromtimestamp(response["sys"]["sunset"], tz=timezone)

        # Liste der Tage generieren
        days_list = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

        # Daten für die Heatmap vorbereiten
        heatmap_data = []
        for day in days_list:
            daily_energies = []
            current_time = timezone.localize(datetime.combine(day, sunrise.time()))
            sunset_time = timezone.localize(datetime.combine(day, sunset.time()))

            while current_time <= sunset_time:
                utc_time = current_time.astimezone(pytz.utc)

                # Solarzenitwinkel mit Pysolar berechnen
                solar_altitude = get_altitude(lat, lon, utc_time)

                if solar_altitude > 0:
                    cloud_factor = (100 - clouds) / 100
                    solar_irradiance = SOLAR_CONSTANT * cloud_factor * (solar_altitude / 90)
                    temperature_factor = 1 + TEMPERATURE_COEFFICIENT * (temp - 25)
                    energy = solar_irradiance * PANEL_AREA * PANEL_EFFICIENCY * temperature_factor * (1 / 3600)
                else:
                    energy = 0  # Keine Energieproduktion, wenn die Sonne unter dem Horizont ist

                daily_energies.append(energy)
                current_time += timedelta(hours=1)

            heatmap_data.append(daily_energies)

        # Gesamte Energie berechnen
        total_energy = np.sum(heatmap_data)
        return total_energy, heatmap_data, days_list, sunrise, sunset, timezone_str
    else:
        st.error(f"❌ API-Fehler für {location}: {response.get('message', 'Unbekannter Fehler')}")
        return None, None, None, None, None, None

# Initialisierung des Session State
if "cities_data" not in st.session_state:
    st.session_state.cities_data = []

# Layout in Spalten aufteilen
col1, col2 = st.columns([1, 2])  # Linke Spalte schmaler, rechte Spalte breiter

# Linke Spalte: Eingabebereich
with col1:
    st.write("### Eingabebereich")
    start_date = st.date_input("Startdatum wählen:", datetime.now(), key="start_date")
    end_date = st.date_input("Enddatum wählen:", datetime.now(), key="end_date")
    new_city = st.text_input("Gib eine Stadt ein:", "Berlin", key="new_city")

    # Button "Bestätigen"
    if st.button("Bestätigen"):
        if new_city:
            # Energieproduktion berechnen
            total_energy, heatmap_data, days_list, sunrise, sunset, timezone_str = calculate_energy(new_city, start_date, end_date)
            if total_energy is not None:
                # Temporäre Speicherung der aktuellen Stadt
                st.session_state.current_city = {
                    "Stadt": new_city,
                    "Gesamtenergie": total_energy,
                    "Heatmap-Daten": heatmap_data,
                    "Tage": days_list,
                    "Sonnenaufgang": sunrise,
                    "Sonnenuntergang": sunset,
                    "Zeitzone": timezone_str,
                    "Startdatum": start_date,
                    "Enddatum": end_date
                }
                st.success(f"Energieproduktion für {new_city} berechnet!")
        else:
            st.warning("Bitte gib eine Stadt ein.")

    # Button "Stadt hinzufügen"
    if "current_city" in st.session_state and st.button("Stadt hinzufügen"):
        st.session_state.cities_data.append(st.session_state.current_city)
        st.success(f"{st.session_state.current_city['Stadt']} wurde zur Liste hinzugefügt!")
        del st.session_state.current_city  # Aktuelle Stadt zurücksetzen

# Rechte Spalte: Diagramme
with col2:
    if st.session_state.cities_data:
        # Überschrift "Energieproduktion pro Stunde und Tag" (zentriert und größer)
        st.markdown(
            "<h2 style='text-align: center; font-size: 30px;'>Energieproduktion pro Stunde und Tag</h2>",
            unsafe_allow_html=True
        )
        for idx, city in enumerate(st.session_state.cities_data):  # Index hinzufügen
            st.write(f"##### {city['Stadt']} (Zeitzone: {city['Zeitzone']})")
            hours = [f"{i}:00" for i in range(len(city['Heatmap-Daten'][0]))]
            days = [day.strftime("%Y-%m-%d") for day in city['Tage']]
            df = pd.DataFrame(city['Heatmap-Daten'], index=days, columns=hours)

            # Heatmap mit Gelb-Rot-Farbpalette
            fig = px.imshow(
                df,
                labels=dict(x="Stunde", y="Tag", color="Energie (Wh)"),
                x=hours,
                y=days,
                color_continuous_scale="YlOrRd",  # Gelb bis Rot
                title=f"Energieproduktion für {city['Stadt']}"
            )
            fig.update_layout(
                xaxis_title="Stunde",
                yaxis_title="Tag",
                coloraxis_colorbar=dict(title="Energie (Wh)")
            )
            # Eindeutiger Schlüssel mit Index
            st.plotly_chart(fig, key=f"heatmap_{city['Stadt']}_{idx}")

# Tabelle ganz unten
if st.session_state.cities_data:
    st.write("### Vergleich der Energieproduktion zwischen den Städten")
    # Tabelle mit Zeitraum und zentrierten Werten
    total_energy_df = pd.DataFrame({
        "Stadt": [city["Stadt"] for city in st.session_state.cities_data],
        "Startdatum": [city["Startdatum"].strftime("%Y-%m-%d") for city in st.session_state.cities_data],
        "Enddatum": [city["Enddatum"].strftime("%Y-%m-%d") for city in st.session_state.cities_data],
        "Gesamtenergie (Wh)": [city["Gesamtenergie"] for city in st.session_state.cities_data]
    })
    # Werte in der Tabelle zentrieren
    st.table(total_energy_df.style.set_properties(**{'text-align': 'center'}).set_table_styles(
        [{'selector': 'th', 'props': [('text-align', 'center')]}]
    ))
else:
    st.warning("Keine Städte eingegeben.")