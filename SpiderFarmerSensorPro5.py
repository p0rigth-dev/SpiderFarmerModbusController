import tkinter as tk
from tkinter import ttk
import serial
import time
import struct
import math
import csv
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --- KONFIGURATION ---
PORT = 'COM10'
BAUD = 115200
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "sensor_log.csv")
DEMO_FILE = os.path.join(LOG_DIR, "demo_log.csv")

# Ordner erstellen falls nicht vorhanden
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def calculate_vpd(temp, rh):
    if rh > 99.9: rh = 99.9
    svp = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
    avp = svp * (rh / 100.0)
    return svp - avp


class GGSProAnalytics:
    def __init__(self, root):
        self.root = root
        self.root.title("Spider Farmer GGS Pro - Ultimate Dashboard")
        self.root.geometry("1200x800")
        self.root.configure(bg="#0f0f0f")

        # Daten-Speicher
        self.history_x = []
        self.history_temp = []
        self.history_hum = []
        self.history_vpd = []
        self.history_ppfd = []

        self.setup_ui()
        self.setup_charts()

        # Initialisierung: Demo-Daten laden, falls vorhanden
        self.load_initial_data()
        self.update_loop()

    def setup_ui(self):
        header = tk.Frame(self.root, bg="#1a1a1a", height=70)
        header.pack(fill="x", side="top")
        tk.Label(header, text="GGS PRO CLIMATE & LIGHT ANALYTICS", font=("Impact", 22),
                 bg="#1a1a1a", fg="#00ffcc").pack(pady=15)

        self.side_panel = tk.Frame(self.root, bg="#0f0f0f", width=300)
        self.side_panel.pack(side="left", fill="y", padx=20, pady=10)

        self.temp_disp = self.create_indicator("TEMPERATUR", "°C", "#ff4d4d")
        self.hum_disp = self.create_indicator("LUFTFEUCHTE", "%", "#3399ff")
        self.vpd_disp = self.create_indicator("VPD (DEFIZIT)", "kPa", "#ffcc00")
        self.ppfd_disp = self.create_indicator("PPFD (PAR)", "µmol", "#00ff66")

    def create_indicator(self, label, unit, color):
        frame = tk.Frame(self.side_panel, bg="#1a1a1a", highlightbackground="#333333", highlightthickness=1)
        frame.pack(fill="x", pady=8)
        tk.Label(frame, text=label, font=("Arial", 9, "bold"), bg="#1a1a1a", fg="gray").pack(pady=(5, 0))
        val_label = tk.Label(frame, text="--.-", font=("Verdana", 28, "bold"), bg="#1a1a1a", fg=color)
        val_label.pack()
        tk.Label(frame, text=unit, font=("Arial", 8), bg="#1a1a1a", fg="gray").pack(pady=(0, 5))
        return val_label

    def setup_charts(self):
        self.chart_frame = tk.Frame(self.root, bg="#0f0f0f")
        self.chart_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.fig = Figure(figsize=(8, 6), dpi=100, facecolor='#0f0f0f')
        self.ax_t = self.fig.add_subplot(221, facecolor='#161616')
        self.ax_h = self.fig.add_subplot(222, facecolor='#161616')
        self.ax_v = self.fig.add_subplot(223, facecolor='#161616')
        self.ax_p = self.fig.add_subplot(224, facecolor='#161616')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def load_initial_data(self):
        """Lädt die letzten 30 Einträge aus der Demo-Datei für die Graphen."""
        if os.path.exists(DEMO_FILE):
            try:
                with open(DEMO_FILE, "r") as f:
                    reader = list(csv.DictReader(f))
                    # Nimm die letzten 30 Zeilen
                    last_entries = reader[-30:] if len(reader) > 30 else reader
                    for row in last_entries:
                        self.history_x.append(row['Timestamp'].split(' ')[1][:5])  # Nur HH:MM
                        self.history_temp.append(float(row['Temp_C']))
                        self.history_hum.append(float(row['Hum_Pct']))
                        self.history_vpd.append(float(row['VPD_kPa']))
                        self.history_ppfd.append(float(row['PPFD_umol']))
                self.refresh_plots()
            except Exception as e:
                print(f"Fehler beim Laden der Demo-Daten: {e}")

    def log_data(self, t, h, v, p):
        for path in [LOG_FILE, DEMO_FILE]:
            exists = os.path.isfile(path)
            with open(path, "a", newline="") as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(["Timestamp", "Temp_C", "Hum_Pct", "VPD_kPa", "PPFD_umol"])
                writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), t, h, v, p])

    def refresh_plots(self):
        plots = [
            (self.ax_t, self.history_temp, "#ff4d4d", "Temperatur (°C)"),
            (self.ax_h, self.history_hum, "#3399ff", "Luftfeuchte (%)"),
            (self.ax_v, self.history_vpd, "#ffcc00", "VPD (kPa)"),
            (self.ax_p, self.history_ppfd, "#00ff66", "PPFD (µmol)")
        ]
        for ax, hist, col, title in plots:
            ax.clear()
            if hist:
                ax.plot(self.history_x, hist, color=col, linewidth=2)
            ax.set_title(title, color="white", fontsize=10)
            ax.tick_params(colors='gray', labelsize=7)
            ax.grid(True, color="#333333", linestyle="--", linewidth=0.5)
        self.fig.tight_layout()
        self.canvas.draw()

    def update_loop(self):
        ser = None
        try:
            ser = serial.Serial(PORT, BAUD, timeout=1.0)
            cmd = bytearray([0x10, 0x03, 0x00, 0x00, 0x00, 0x1C, 0x47, 0x42])
            ser.write(cmd)
            res = ser.read(61)

            if len(res) >= 59:
                idx = res.find(b'\x10\x03\x38')
                if idx != -1:
                    data = res[idx + 3: idx + 59]
                    regs = struct.unpack('>' + 'H' * 28, data)

                    t, h = regs[10] / 10.0, regs[11] / 10.0
                    v = calculate_vpd(t, h)
                    p = (regs[13] + regs[14]) / 2

                    self.temp_disp.config(text=f"{t:.1f}")
                    self.hum_disp.config(text=f"{h:.1f}")
                    self.vpd_disp.config(text=f"{v:.2f}")
                    self.ppfd_disp.config(text=f"{p:.0f}")

                    self.history_x.append(time.strftime('%H:%M'))
                    self.history_temp.append(t)
                    self.history_hum.append(h)
                    self.history_vpd.append(v)
                    self.history_ppfd.append(p)

                    if len(self.history_x) > 30:
                        for attr in [self.history_x, self.history_temp, self.history_hum, self.history_vpd,
                                     self.history_ppfd]:
                            attr.pop(0)

                    self.refresh_plots()
                    self.log_data(t, h, v, p)

        except Exception as e:
            print(f"Fehler: {e}")
        finally:
            if ser: ser.close()

        self.root.after(30000, self.update_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app = GGSProAnalytics(root)
    root.mainloop()