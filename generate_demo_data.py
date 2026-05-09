import csv
import os
import math
import random
from datetime import datetime, timedelta

LOG_DIR = "logs"
DEMO_FILE = os.path.join(LOG_DIR, "demo_log.csv")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def calculate_vpd(temp, rh):
    if rh > 99.9: rh = 99.9
    svp = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
    avp = svp * (rh / 100.0)
    return svp - avp


def generate_demo_data(entries=100):
    print(f"Generiere {entries} Demo-Einträge in {DEMO_FILE}...")

    # Startzeit vor 'entries' Intervallen (angenommen 10 Min pro Eintrag)
    start_time = datetime.now() - timedelta(minutes=10 * entries)

    # Datei neu schreiben (oder 'a' für anhängen)
    with open(DEMO_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Temp_C", "Hum_Pct", "VPD_kPa", "PPFD_umol"])

        for i in range(entries):
            current_time = start_time + timedelta(minutes=10 * i)
            hour = current_time.hour

            # Simulation: Licht an von 06:00 bis 18:00
            if 6 <= hour < 18:
                ppfd = random.uniform(800, 850)  # Stabil unter Lampe
                temp = random.uniform(26.0, 29.5)  # Wärmer
                hum = random.uniform(45.0, 55.0)  # Mittlere Feuchte
            else:
                ppfd = random.uniform(0, 5)  # Dunkel
                temp = random.uniform(19.0, 22.0)  # Kühler
                hum = random.uniform(60.0, 70.0)  # Feuchter nachts

            vpd = calculate_vpd(temp, hum)

            writer.writerow([
                current_time.strftime('%Y-%m-%d %H:%M:%S'),
                round(temp, 2),
                round(hum, 2),
                round(vpd, 2),
                round(ppfd, 2)
            ])

    print("Fertig! Du kannst das Dashboard jetzt starten.")


if __name__ == "__main__":
    generate_demo_data(144)  # 144 Einträge = 24 Stunden bei 10-Min-Takt