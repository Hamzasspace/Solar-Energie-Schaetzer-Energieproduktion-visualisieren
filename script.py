import streamlit as st
from datetime import datetime, timedelta
import pytz
from timezonefinder import TimezoneFinder
from pysolar.solar import get_altitude
import ephem
import requests
import matplotlib.pyplot as plt

#Streamlit-App Titel
st.title("☀️ Solar-Energie-Schätzer")

# Benutzereingabe
location = st.text_input("Gib eine Stadt ein:", "Berlin")
date_input = st.date_input("Gib das Datum ein:", datetime.now(), key="date_input_unique_key")

# API-Schlüssel für OpenWeatherMap
api_key = "b3a160e9fec8f37993c763aa1923c8f8"
# Wetterdaten abrufen
#Eine HTTP-Anfrage wird an die OpenWeatherMap API gesendet, um Wetterdaten für die eingegebene Stadt abzurufen
#Die Antwort wird im JSON-Format zurückgegeben.
url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
response = requests.get(url).json()

# Konstanten
PANEL_EFFICIENCY = 0.18  
PANEL_AREA = 10  
SOLAR_CONSTANT = 1361
TEMPERATURE_COEFFICIENT = -0.005 #Er bedeutet, dass die Effizienz der Solarpanels um 0,5 % pro Grad Celsius über 25 °C abnimmt.

# Zeitumwandlung
date_input = st.date_input("Gib das Datum ein:", datetime.now())
date_obj = date_input  # date_input ist bereits ein datetime.date-Objekt
start_time = datetime.combine(date_obj, datetime.min.time())
end_time = datetime.combine(date_obj, datetime.max.time())  

if response.get("cod") == 200: #Überprüfung der API-Antwort
    lat = response["coord"]["lat"] #lat: Breitengradder Stadt
    lon = response["coord"]["lon"] #lon: Längengrad der Stadt
    clouds = response["clouds"]["all"] #clouds: Bewölkung in Prozent.
    temp = response["main"]["temp"]# temp: Temperatur in °C.

    # Zeitzone bestimmen
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    timezone = pytz.timezone(timezone_str)

    # Lokale Zeiten setzen: Die Start- und Endzeiten werden mit der lokalen Zeitzone versehen.
    start_time = timezone.localize(start_time)
    end_time = timezone.localize(end_time)

    # Sonnenaufgang & -untergang: Die Zeiten für Sonnenaufgang und Sonnenuntergang werden aus der API-Antwort extrahiert und in die lokale Zeitzone umgewandelt.
    sunrise = datetime.fromtimestamp(response["sys"]["sunrise"], tz=timezone)
    sunset = datetime.fromtimestamp(response["sys"]["sunset"], tz=timezone)
    #Ausgabe der Standort- und Zeitinformationen
    st.write(f"🌍 Stadt: {location} ({lat}, {lon})")
    st.write(f"🕰 Zeitzone: {timezone_str}")
    st.write(f"🌅 Sonnenaufgang: {sunrise}, 🌇 Sonnenuntergang: {sunset}")

    # Startwerte
    current_time = sunrise  # Die Berechnung beginnt beim Sonnenaufgang.
    total_energy = 0 #Speichert die gesamte geschätzte Solarenergie des Tages. 
    # Listen zur Speicherung der Zeitpunkte und Energiewerte
    times = []
    energies = []
    
    while current_time <= sunset:  # Nur Sonnenstunden berücksichtigen
        utc_time = current_time.astimezone(pytz.utc)  # Die lokale Zeit wird in UTC umgewandelt, da pysolar und ephem UTC-Zeiten benötigen.

        # 🌞 Solarzenitwinkel mit Pysolar berechnen
        solar_altitude = get_altitude(lat, lon, utc_time)

        # 🌞 Sonnenhöhe(Solarzenitwinkel) mit Ephem Berechnung
        observer = ephem.Observer()
        observer.lat, observer.lon = str(lat), str(lon)
        observer.date = utc_time.strftime("%Y/%m/%d %H:%M:%S")
        sun = ephem.Sun(observer)
        solar_altitude_ephem = sun.alt * (180 / 3.1415926535) #Die Formel sun.alt * (180 / 3.1415926535) wandelt den Winkel von Radiant (dem Standard in ephem) in Grad um

        # Debugging-Ausgabe
        print(f"\n🕒 {current_time} (Lokal), {utc_time} (UTC)")
        print(f"☀️ Sonnenhöhe Pysolar: {solar_altitude:.2f}°")
        print(f"☀️ Sonnenhöhe Ephem: {solar_altitude_ephem:.2f}°")

        # Wenn die Sonne über dem Horizont ist
        if solar_altitude > 0:
            cloud_factor = (100 - clouds) / 100 #Skaliert die Sonneneinstrahlung basierend auf der Bewölkung (clouds)
            solar_irradiance = SOLAR_CONSTANT * cloud_factor * (solar_altitude / 90) #Berechnet die Sonneneinstrahlung in W/m²
            #Korrigiert die Effizienz basierend auf der Temperatur.
      
            temperature_factor = 1 + TEMPERATURE_COEFFICIENT * (temp - 25) #25: Die Standardtesttemperatur 25°C
            #Berechnet die geschätzte Energieproduktion in Wattstunden (Wh)
            energy = solar_irradiance * PANEL_AREA * PANEL_EFFICIENCY * temperature_factor * (1 / 3600) #1/3600:von Wattsekunden (Ws) in Wattstunden (Wh) umzurechnen.
            total_energy += energy
            
             # Speichern der Zeit und Energie in den Listen
            times.append(current_time)
            energies.append(energy)
            #Gibt die berechnete Sonneneinstrahlung und Energieproduktion aus
            print(f"🔆 Einstrahlung: {solar_irradiance:.2f} W/m²")
            print(f"⚡ Energie: {energy:.2f} Wh")
        else:
            print("❌ Sonne nicht über dem Horizont.")
        #Die Schleife wird für die nächste Stunde fortgesetzt.
        current_time += timedelta(hours=1)
    #Gibt die gesamte geschätzte Solarenergie des Tages aus.
    print(f"\n⚡ Gesamte geschätzte Solarenergie: {total_energy:.2f} Wh")

    # Debugging-Ausgaben
    print(f"\nDEBUG: UTC-Zeit für Pysolar = {utc_time}")
    print(f"DEBUG: Ephem Sonnenhöhe = {solar_altitude_ephem}°")
    print(f"DEBUG: Pysolar Sonnenhöhe = {solar_altitude}°")
    print(f"DEBUG: Sonnenaufgang: {sunrise}, Sonnenuntergang: {sunset}")
    print(f"DEBUG: Bewölkung: {clouds}%, Temperatur: {temp}°C")
    #Fehlerbehandlung
else:#Falls die API-Anfrage fehlschlägt, wird eine Fehlermeldung ausgegeben
    print(f"❌ API-Fehler: {response.get('message', 'Unbekannter Fehler')}")

#Diagramm der Energieproduktion
st.write("Energieproduktion über den Tag")
fig, ax = plt.subplots()
ax.plot(times, energies, marker="o")
ax.set_xlabel("Uhrzeit")
ax.set_ylabel("Energie (Wh)")
plt.xticks(rotation=45)  # Dreht die x-Achsenbeschriftungen für bessere Lesbarkeit
st.pyplot(fig)

# Gesamte Energie
st.write(f"### ⚡ Gesamte geschätzte Solarenergie: {total_energy:.2f} Wh")
