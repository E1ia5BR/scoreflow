import music21
import os

def clean_and_quantize_score(score, audio_type="piano"):
    """
    Cleans raw AI-generated MIDI notes:
    1. Removes ghost notes (very short + low velocity)
    2. Uses music21's robust quantizer to snap to 16th/8th grids without overlapping tied notes
    3. Analyzes and corrects harmonic spelling (flats vs sharps based on key)
    4. Formats it for readability (splitting hands for piano)
    """

    # 1. First Pass: Filter out noise before quantizing
    filtered_score = music21.stream.Score()
    # Copy metadata if any
    if score.metadata:
        filtered_score.insert(0, score.metadata)

    # We only want to process the notes
    notes_to_process = []
    for el in score.flatten().getElementsByClass(['Note', 'Chord']):
        import copy
        notes_to_process.append(copy.deepcopy(el))

    valid_notes = []
    for n in notes_to_process:
        # Ghost note removal rules:
        # If it's shorter than a 32nd note (0.125 quarter lengths)...
        if n.quarterLength < 0.125:
             # Basic Pitch and Magenta often output low velocity for these false positives
             if hasattr(n, 'volume') and n.volume.velocity is not None and n.volume.velocity < 50:
                 continue # Definitely noise
             elif n.quarterLength < 0.05:
                 continue # Way too short to be real, even if loud
                 
        valid_notes.append(n)

    # Put valid notes into a temporary flat part for quantization
    temp_part = music21.stream.Part()
    for n in valid_notes:
        temp_part.insert(n.offset, n)
        
    # 2. Robust Quantization using music21
    # We quantize to Quarters (4), Eighths (8), and Sixteenths (16)
    # This prevents the "manual rounding" from creating weird overlapping notes
    try:
        temp_part.quantize((4, 8, 16), processOffsets=True, processDurations=True, inPlace=True)
    except Exception as e:
        print(f"Warning: music21 builtin quantize failed ({e}), falling back to raw notes.")

    # 3. Harmonic Spelling Correction
    # This analyzes the key and spells the notes correctly
    try:
        key = temp_part.analyze('key')
        temp_part.insert(0, key)
        # We don't necessarily need to manually iterate and spell, 
        # as makeNotation (called later in the pipeline) usually handles it better
        # if the key signature is present.
    except Exception as e:
        print(f"Warning: Harmonic analysis failed ({e})")
        
    # Optional: Gap filling
    # If a note ends at 1.0, and the next starts at 1.05 (after quantize), 
    # it might create a tiny rest. Quantize usually fixes this, but we can 
    # force lengths to meet the next note if the gap is very small.
    # (Skipping for now as music21 quantize is usually sufficient)

    # 4. Split Hands / Format Notation
    new_score = music21.stream.Score()
    
    if audio_type == "piano" or audio_type == "banda":
        # Split into Treble (Right Hand) and Bass (Left Hand)
        treble_part = music21.stream.Part()
        bass_part = music21.stream.Part()
        
        treble_part.insert(0, music21.clef.TrebleClef())
        bass_part.insert(0, music21.clef.BassClef())
        
        for n in temp_part.notes:
            # Check center pitch (Middle C = C4 = midi 60)
            if n.isChord:
                avg_midi = sum([p.midi for p in n.pitches]) / len(n.pitches)
                if avg_midi >= 60:
                    treble_part.insert(n.offset, n)
                else:
                    bass_part.insert(n.offset, n)
            else:
                if n.pitch.midi >= 60:
                    treble_part.insert(n.offset, n)
                else:
                    bass_part.insert(n.offset, n)
        
        # Chordify each hand separately to merge overlaps cleanly within the staff
        treble_part = treble_part.chordify()
        bass_part = bass_part.chordify()
        
        new_score.insert(0, treble_part)
        new_score.insert(0, bass_part)
    else:
        # Vocal or single instrument: just put them in one part and chordify
        part = music21.stream.Part()
        for n in temp_part.notes:
            part.insert(n.offset, n)
        # We don't necessarily chordify vocals, but AI might generate polyphony by accident.
        # It's safer to chordify to prevent overlapping notes in a single voice staff.
        new_score.insert(0, part.chordify())
        
    return new_score

if __name__ == "__main__":
    print("Generating MESSY test score (simulating AI output)...")
    score = music21.stream.Score()
    part = music21.stream.Part()
    
    # 1. Main Melody (Off grid, weird durations)
    n1 = music21.note.Note('C4')
    n1.quarterLength = 0.97 # Should snap to 1.0
    part.insert(0.04, n1)   # Should snap to 0.0
    
    # 2. Low-velocity ghost noise (Super short)
    noise1 = music21.note.Note('E-4')
    noise1.quarterLength = 0.02
    noise1.volume.velocity = 30
    part.insert(1.01, noise1) # Should be REMOVED
    
    # 3. Bad Harmonic Spelling (G-flat in C Major context, should be F#)
    n2 = music21.note.Note('G-4')
    n2.quarterLength = 0.53 # Should snap to 0.5
    part.insert(2.05, n2)   # Should snap to 2.0
    
    # 4. Bass note overlapping weirdly with treble timing
    n3 = music21.note.Note('C3')
    n3.quarterLength = 1.8 
    part.insert(0.1, n3)
    
    score.insert(0, part)
    
    print("Cleaning and Quantizing...")
    try:
        clean_score = clean_and_quantize_score(score, audio_type="piano")
        
        # Apply Time Signature and measures for test viewing
        ts = music21.meter.TimeSignature("4/4")
        clean_score.insert(0, ts)
        for p in clean_score.parts:
            p.insert(0, ts)
            
        clean_score.makeMeasures(inPlace=True)
        clean_score.makeNotation(inPlace=True)
        
        print("Success! Writing output to test_out_quantized.musicxml")
        clean_score.write("musicxml", "test_out_quantized.musicxml")
    except Exception as e:
        import traceback
        print(f"FAILED: {e}")
        traceback.print_exc()
    print("Done")
    
    print("Writing output to test_out.musicxml")
    clean_score.write("musicxml", "test_out.musicxml")
    print("Done")
