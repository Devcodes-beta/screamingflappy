import sounddevice as sd

print(sd.query_devices())
print("\nDefault input device:", sd.default.device)
