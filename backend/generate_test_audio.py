import wave
import struct
import math

# Parameters
nchannels = 1
sampwidth = 2
framerate = 44100
note_duration = int(44100 * 0.5)  # 0.5 seconds per note
comptype = "NONE"
compname = "not compressed"
volume = 32767.0 / 2

# Notes: C4, E4, G4, C5
frequencies = [261.63, 329.63, 392.00, 523.25]
nframes = note_duration * len(frequencies)

with wave.open('test_real.wav', 'w') as wav_file:
    wav_file.setparams((nchannels, sampwidth, framerate, nframes, comptype, compname))
    for freq in frequencies:
        for i in range(note_duration):
            value = int(volume * math.sin(2.0 * math.pi * freq * i / framerate))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)
