"""
================================================================================
SPIDER FARMER MODBUS CONTROLLER - GUI v1.2
================================================================================
WICHTIGER HINWEIS:
    Dieses Programm ist KEIN offizielles Produkt von Spider Farmer®.
    Es handelt sich um eine unabhängige Entwicklung (Community-Projekt).
    Es besteht keine Verbindung, Autorisierung oder Unterstützung durch
    die Spider Farmer Company.

HAFTUNGSAUSSCHLUSS / DISCLAIMER:
    Die Verwendung dieses Skripts und der Hardware-Eingriff erfolgen auf
    eigene Gefahr. Es wird keine Haftung für Schäden an der Lampe, dem
    Controller oder angeschlossener Hardware übernommen. Durch unsachgemäße
    Verkabelung oder Modifikation kann die Herstellergarantie erlöschen.
    Jegliche Haftung für Sach- oder Personenschäden ist ausgeschlossen.

Beschreibung:
    Dieses Skript steuert eine Spider Farmer LED-Lampe über das Modbus RTU
    Protokoll. Es bietet eine grafische Oberfläche (Dark Mode) mit einem
    interaktiven Tachometer und Echtzeit-Steuerung.

Hardware-Setup:
    - Modus: Lampe muss auf 'Linked' stehen.
    - Dongle: USB-zu-RS485 Adapter erforderlich.
    - RJ12 Pinout:
        Pin 3 = RS485-A (Data+) [Rot]
        Pin 6 = RS485-B (Data-) [Blau]

Paketaufbau (18 Bytes Binär):
    [0-1]   Magic Header: 0xAAAA
    [2-3]   Msg Type:     0x0001 (Unverschlüsselt)
    [4-5]   Command ID:   0x000A (Dimmungs-Kommando)
    [6-11]  Quell-MAC:    6 Bytes (Identität des Masters)
    [12-13] Dimmer:       2 Bytes (0x0000 - 0x0064)
    [14-15] Power:        2 Bytes (0x0000 = AUS, 0x0001 = AN)
    [16-17] Checksum:     2 Bytes (CRC16-Modbus, Big-Endian)

================================================================================
"""
import tkinter as tk
from tkinter import ttk
import serial
import threading
import time
import struct
import math

# ================================================================================
# --- KONFIGURATION ---
# ================================================================================

# Der serielle Port, an dem dein RS485-Adapter angeschlossen ist.
# Windows: 'COMx' (z.B. 'COM10') | Linux: '/dev/ttyUSBx'
SERIAL_PORT = 'COM10'

# Die Übertragungsgeschwindigkeit. Standard für die meisten Spider Farmer
# Controller ist 9600 Baud.
BAUDRATE = 9600

# Die 6-Byte Identifikationsnummer (MAC) deiner Lampe oder deines Controllers.
# Muss als 12-stelliger Hex-String (0-9, A-F) ohne Trennzeichen angegeben werden.
# Muss keine reale mac sein kann man so lassen wie es hier ist.
LAMPE_MAC = "0123456789AB"

# Schwellenwert der Lampe: Da Spider Farmer Lampen oft ein physikalisches
# Minimum zum Zünden der LEDs benötigen, verhindert dieser Wert ein
# ungewolltes Flackern oder Glimmen im zu niedrigen Bereich.
# Der Slider startet bei diesem Wert; beim Einschalten wird dieser Wert als Basis genutzt.
MIN_BRIGHTNESS = 11

# ================================================================================

# --- FARBEN ---
BG_DARK = "#1E1E1E"
FG_LIGHT = "#FFFFFF"
ACCENT_GREEN = "#2ECC71"
ACCENT_RED = "#E74C3C"
GAUGE_COLOR = "#333333"


class SpiderFarmerControl:
    def __init__(self, root):
        self.root = root
        self.root.title("Spider Farmer Modbus Controller")
        self.root.geometry("450x600")
        self.root.configure(bg=BG_DARK)

        self.brightness = 0
        self.is_on = False
        self.running = True
        self.serial_lock = threading.Lock()

        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
        except Exception as e:
            print(f"Port Fehler: {e}")
            self.ser = None

        self.setup_ui()

        self.loop_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.loop_thread.start()

    def calculate_crc16_modbus(self, data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def create_frame(self):
        header = bytes.fromhex("AAAA")
        msg_type = bytes.fromhex("0001")
        command = bytes.fromhex("000A")
        clean_mac = "".join(c for c in LAMPE_MAC if c in "0123456789abcdefABCDEF")
        if len(clean_mac) != 12: return None
        mac_bytes = bytes.fromhex(clean_mac)

        dim_val = int(self.brightness) if self.is_on else 0
        power_val = 1 if self.is_on else 0

        dim_bytes = struct.pack(">H", dim_val)
        power_bytes = struct.pack(">H", power_val)

        packet_so_far = header + msg_type + command + mac_bytes + dim_bytes + power_bytes
        crc_val = self.calculate_crc16_modbus(packet_so_far)
        return packet_so_far + struct.pack(">H", crc_val)

    def send_now(self):
        if self.ser and self.ser.is_open:
            frame = self.create_frame()
            if frame:
                with self.serial_lock:
                    self.ser.write(frame)
                print(f"TX: {frame.hex().upper()}")

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=BG_DARK, padx=30, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- TACHOMETER (CANVAS) ---
        self.canvas = tk.Canvas(main_frame, width=300, height=180, bg=BG_DARK, highlightthickness=0)
        self.canvas.pack(pady=10)
        self.draw_gauge()

        # Prozentanzeige groß unter Tacho
        self.perc_label = tk.Label(main_frame, text="0 %", bg=BG_DARK, fg=FG_LIGHT, font=('Arial', 28, 'bold'))
        self.perc_label.pack()

        # Status Label (kleiner darunter)
        self.status_label = tk.Label(main_frame, text="System OFF", bg=BG_DARK, fg=ACCENT_RED,
                                     font=('Arial', 10, 'bold'))
        self.status_label.pack(pady=(0, 20))

        # --- SLIDER (QUER) ---
        tk.Label(main_frame, text="DIMMER", bg=BG_DARK, fg=FG_LIGHT, font=('Arial', 9, 'bold')).pack()
        self.scale = tk.Scale(main_frame, from_=MIN_BRIGHTNESS, to=100, orient=tk.HORIZONTAL,
                              command=self.on_slider_change, length=300,
                              bg=BG_DARK, fg=FG_LIGHT, highlightthickness=0,
                              troughcolor=GAUGE_COLOR, activebackground=ACCENT_GREEN)
        self.scale.pack(pady=20)

        # Trenner
        tk.Frame(main_frame, height=2, bg=GAUGE_COLOR).pack(fill=tk.X, pady=20)

        # --- POWER BUTTONS ---
        btn_frame = tk.Frame(main_frame, bg=BG_DARK)
        btn_frame.pack(fill=tk.X)

        self.btn_on = tk.Button(btn_frame, text="ON", command=self.power_on,
                                bg="#333333", fg=FG_LIGHT, font=('Arial', 14, 'bold'),
                                relief=tk.FLAT, height=2)
        self.btn_on.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_off = tk.Button(btn_frame, text="OFF", command=self.power_off,
                                 bg="#333333", fg=FG_LIGHT, font=('Arial', 14, 'bold'),
                                 relief=tk.FLAT, height=2)
        self.btn_off.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def draw_gauge(self):
        """Zeichnet den Hintergrund des Tachometers."""
        # Bogen zeichnen (von 180° bis 0°)
        self.canvas.create_arc(10, 20, 290, 300, start=0, extent=180,
                               outline=GAUGE_COLOR, width=15, style=tk.ARC)
        # Nadel initialisieren
        self.needle = self.canvas.create_line(150, 160, 150, 40, fill=ACCENT_RED, width=4)
        # Mittelpunkt
        self.canvas.create_oval(140, 150, 160, 170, fill=FG_LIGHT, outline=BG_DARK)

    def update_needle(self, value):
        """Bewegt die Tachonadel basierend auf 0-100%."""
        # Winkel berechnen: 0% = 180 Grad, 100% = 0 Grad
        angle = 180 - (float(value) * 1.8)
        rad = math.radians(angle)

        # Endpunkt der Nadel (Länge 110)
        x = 150 + 110 * math.cos(rad)
        y = 160 - 110 * math.sin(rad)
        self.canvas.coords(self.needle, 150, 160, x, y)

        # Farbe der Nadel ändern, wenn Power ON
        self.canvas.itemconfig(self.needle, fill=ACCENT_GREEN if self.is_on else ACCENT_RED)

    def on_slider_change(self, val):
        self.brightness = float(val)
        self.is_on = True
        self.update_ui_state()
        self.send_now()

    def power_on(self):
        self.is_on = True
        if self.brightness < MIN_BRIGHTNESS:
            self.brightness = MIN_BRIGHTNESS
            self.scale.set(MIN_BRIGHTNESS)
        self.update_ui_state()
        self.send_now()

    def power_off(self):
        self.is_on = False
        self.update_ui_state()
        self.send_now()

    def update_ui_state(self):
        current_val = int(self.brightness) if self.is_on else 0
        self.perc_label.config(text=f"{current_val} %")
        self.update_needle(current_val)

        if self.is_on:
            self.status_label.config(text="SYSTEM ACTIVE", fg=ACCENT_GREEN)
            self.btn_on.config(bg=ACCENT_GREEN, fg=BG_DARK)
            self.btn_off.config(bg="#333333", fg=FG_LIGHT)
        else:
            self.status_label.config(text="SYSTEM STANDBY", fg=ACCENT_RED)
            self.btn_off.config(bg=ACCENT_RED, fg=FG_LIGHT)
            self.btn_on.config(bg="#333333", fg=FG_LIGHT)

    def heartbeat_loop(self):
        while self.running:
            self.send_now()
            time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    app = SpiderFarmerControl(root)
    root.mainloop()