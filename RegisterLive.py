import serial
import time
import struct

PORT = 'COM10'
BAUD = 115200


def diagnose_ggs_pro():
    ser = None
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.2)
        ser.open() if not ser.is_open else None
        ser.reset_input_buffer()

        # Abfrage 28 Register
        cmd = bytearray.fromhex("10 03 00 00 00 1C 47 42")
        ser.write(cmd)
        ser.flush()

        response = ser.read(61)
        if len(response) >= 59:
            idx = response.find(b'\x10\x03\x38')
            if idx != -1:
                data = response[idx + 3: idx + 59]
                regs = struct.unpack('>' + 'H' * 28, data)

                print("\n--- Register Live-Ansicht ---")
                # Wir geben die Register in 4er Blöcken aus
                for i in range(0, 28, 4):
                    line = ""
                    for j in range(i, i + 4):
                        if j < 28:
                            line += f"Reg[{j:02d}]: {regs[j]:<7} "
                    print(line)

                # Vermutung NEU basierend auf Spider-Farmer Standard:
                # Reg 08 oder 09 sind oft Licht/PPFD
                # Reg 13 oder 14 sind oft VPD

    except Exception as e:
        print(f"Fehler: {e}")
    finally:
        if ser: ser.close()


if __name__ == "__main__":
    while True:
        diagnose_ggs_pro()
        time.sleep(2)