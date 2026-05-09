import serial
import time
import struct
import math

PORT = 'COM10'
BAUD = 115200


def calculate_vpd(temp, rel_hum):
    """Berechnet das Sättigungsdefizit (VPD) in kPa."""
    # Sättigungsdampfdruck (SVP) in kPa
    svp = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
    # Tatsächlicher Dampfdruck (AVP)
    avp = svp * (rel_hum / 100.0)
    # VPD = Defizit
    return svp - avp


def read_ggs_pro_calculated():
    ser = None
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.2)
        ser.dtr = False
        ser.rts = False
        time.sleep(0.1)
        ser.reset_input_buffer()

        # Wir fragen weiterhin 28 Register ab
        cmd = bytearray.fromhex("10 03 00 00 00 1C 47 42")
        ser.write(cmd)
        ser.flush()

        response = ser.read(61)
        if response and len(response) >= 59:
            idx = response.find(b'\x10\x03\x38')
            if idx != -1:
                data = response[idx + 3: idx + 59]
                regs = struct.unpack('>' + 'H' * 28, data)

                # Basiswerte (Reg 10 & 11 bewegen sich!)
                raw_temp = regs[10]
                temp = raw_temp / 10.0 if raw_temp < 32768 else (raw_temp - 65536) / 10.0
                hum = regs[11] / 10.0

                # VPD live berechnet
                vpd = calculate_vpd(temp, hum)

                print("\n" + "=" * 35)
                print(f"Temperatur:   {temp:6.1f} °C")
                print(f"Feuchtigkeit:  {hum:6.1f} % RH")
                print(f"VPD (ber.):    {vpd:6.2f} kPa")

                # Check ob PPFD sich in Reg 8 oder 9 versteckt (war im Log 0)
                ppfd_candidate = regs[8] if regs[8] > 0 else regs[9]
                print(f"Licht (PPFD?): {ppfd_candidate:6d} µmol/m²s")
                print("=" * 35)
            else:
                print("Header nicht gefunden.")
        else:
            print("Keine Antwort.")

    except Exception as e:
        print(f"Fehler: {e}")
    finally:
        if ser:
            ser.close()


if __name__ == "__main__":
    while True:
        read_ggs_pro_calculated()
        time.sleep(2)