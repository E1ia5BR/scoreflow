# test_music_intelligence.py
# ===========================
# Teste isolado do modulo music_intelligence.py
#
# Executa sem precisar do Docker, Celery ou qualquer audio real.
# Cria partituras sinteticas com fragmentacoes ritmicas e verifica
# se o modulo as funde corretamente em figuras musicais maiores.
#
# Uso:
#   cd backend
#   .\\venv\\Scripts\\activate
#   python test_music_intelligence.py


import sys
import os

# Garante que o backend está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import music21
from music21 import note, chord, stream, meter, tempo as m21tempo

from music_intelligence import (
    choose_rhythmic_grid,
    defragment_rhythms,
    apply_musical_intelligence,
    quantize_by_pattern
)

PASS = "[OK] "
FAIL = "[FALHA] "
WARN = "[AVISO] "

results = []

def check(desc: str, condition: bool, detail: str = ""):
    icon = PASS if condition else FAIL
    msg = f"{icon}{desc}"
    if detail:
        msg += f" → {detail}"
    print(msg)
    results.append(condition)

# ---------------------------------------------------------------------------
# HELPER: cria um score simples com notas inseridas manualmente
# ---------------------------------------------------------------------------

def make_score(notes_data, clef_class=None, bpm=120.0):
    """
    notes_data: lista de (pitch_str_ou_None, quarterLength, offset_abs)
               pitch_str_ou_None=None significa Rest

    Retorna um music21.stream.Score com uma Part e um MetronomeMark.
    """
    s = stream.Score()
    mm = m21tempo.MetronomeMark(number=bpm)
    s.insert(0, mm)
    p = stream.Part()
    if clef_class:
        p.insert(0, clef_class())
    for pitch_str, ql, off in notes_data:
        if pitch_str is None:
            r = music21.note.Rest()
            r.quarterLength = ql
            p.insert(off, r)
        else:
            n = note.Note(pitch_str)
            n.quarterLength = ql
            p.insert(off, n)
    s.insert(0, p)
    return s


# ===========================================================================
# TESTE 1: Grade rítmica adaptativa
# ===========================================================================
print("\n" + "="*60)
print("TESTE 1 — Grade rítmica adaptativa ao andamento")
print("="*60)

grid_lento = choose_rhythmic_grid(50, "4/4")
check("BPM 50 (lento) inclui fusas (32)", 32 in grid_lento,
      f"grade={grid_lento}")

grid_normal = choose_rhythmic_grid(100, "4/4")
check("BPM 100 (normal) inclui semicolcheias (16)", 16 in grid_normal,
      f"grade={grid_normal}")

grid_rapido = choose_rhythmic_grid(180, "4/4")
check("BPM 180 (rápido) NÃO inclui semicolcheias (16)", 16 not in grid_rapido,
      f"grade={grid_rapido}")

grid_68 = choose_rhythmic_grid(120, "6/8")
check("Compasso 6/8 começa em denominador 8+", all(g >= 8 for g in grid_68),
      f"grade={grid_68}")


# ===========================================================================
# TESTE 2: Duas semínimas de C4 → mínima de C4
# ===========================================================================
print("\n" + "="*60)
print("TESTE 2 — Duas semínimas → mínima")
print("="*60)

score2 = make_score([
    ("C4", 1.0, 0.0),   # semínima
    ("C4", 1.0, 1.0),   # semínima — deve ser fundida com a anterior
    ("E4", 1.0, 2.0),   # nota diferente — NÃO deve ser fundida
    ("G4", 0.5, 3.0),   # outra nota diferente
], bpm=120.0)

result2 = defragment_rhythms(score2, "4/4", bpm=120.0)
notes2 = list(result2.flatten().getElementsByClass(['Note']))

c4_notes = [n for n in notes2 if n.nameWithOctave == 'C4']
check("Duas semínimas C4 → 1 única nota", len(c4_notes) == 1,
      f"encontradas {len(c4_notes)} nota(s) C4")
if c4_notes:
    check("Duração da C4 fundida = mínima (2.0)", abs(c4_notes[0].quarterLength - 2.0) < 0.05,
          f"quarterLength={c4_notes[0].quarterLength}")

other_notes = [n for n in notes2 if n.nameWithOctave != 'C4']
check("E4 e G4 não foram fundidas (pitches diferentes)", len(other_notes) == 2,
      f"{[n.nameWithOctave for n in other_notes]}")


# ===========================================================================
# TESTE 3: Semínima + colcheia → semínima pontuada
# ===========================================================================
print("\n" + "="*60)
print("TESTE 3 — Semínima + colcheia → semínima pontuada")
print("="*60)

score3 = make_score([
    ("D4", 1.0, 0.0),   # semínima
    ("D4", 0.5, 1.0),   # colcheia — deve fundir → 1.5 QL (semínima pontuada)
    ("D4", 0.5, 1.5),   # mais uma colcheia — pode fundir com a anterior ou não
], bpm=90.0)

result3 = defragment_rhythms(score3, "4/4", bpm=90.0)
notes3 = [n for n in result3.flatten().getElementsByClass(['Note'])
          if n.nameWithOctave == 'D4']

total_ql = sum(n.quarterLength for n in notes3)
check("Duração total de D4 preservada (= 2.0 QL)", abs(total_ql - 2.0) < 0.05,
      f"total={total_ql:.2f}")

check("Menos notas D4 após fusão", len(notes3) < 3,
      f"restaram {len(notes3)} nota(s)")


# ===========================================================================
# TESTE 4: Quatro colcheias de G4 → mínima
# ===========================================================================
print("\n" + "="*60)
print("TESTE 4 — Quatro colcheias do mesmo pitch → mínima")
print("="*60)

score4 = make_score([
    ("G4", 0.5, 0.0),
    ("G4", 0.5, 0.5),
    ("G4", 0.5, 1.0),
    ("G4", 0.5, 1.5),
], bpm=120.0)

result4 = defragment_rhythms(score4, "4/4", bpm=120.0)
notes4 = [n for n in result4.flatten().getElementsByClass(['Note'])
          if n.nameWithOctave == 'G4']

check("4 colcheias G4 → 1 nota", len(notes4) == 1,
      f"encontradas {len(notes4)} nota(s)")
if notes4:
    check("Duração = mínima (2.0)", abs(notes4[0].quarterLength - 2.0) < 0.05,
          f"quarterLength={notes4[0].quarterLength}")


# ===========================================================================
# TESTE 5: Notas em pitches diferentes NÃO são fundidas
# ===========================================================================
print("\n" + "="*60)
print("TESTE 5 — Pitches diferentes NÃO são fundidos")
print("="*60)

score5 = make_score([
    ("C4", 1.0, 0.0),
    ("D4", 1.0, 1.0),  # pitch diferente — não deve fundir
    ("E4", 1.0, 2.0),
    ("F4", 1.0, 3.0),
], bpm=120.0)

result5 = defragment_rhythms(score5, "4/4", bpm=120.0)
notes5 = list(result5.flatten().getElementsByClass(['Note']))
check("4 notas de pitches diferentes mantêm 4 notas", len(notes5) == 4,
      f"encontradas {len(notes5)} nota(s)")


# ===========================================================================
# TESTE 6: Pipeline completo apply_musical_intelligence
# ===========================================================================
print("\n" + "="*60)
print("TESTE 6 — Pipeline completo apply_musical_intelligence")
print("="*60)

# Cria um score cheio de fragmentações típicas da IA
score6 = stream.Score()
mm6 = m21tempo.MetronomeMark(number=110)
score6.insert(0, mm6)
p6 = stream.Part()
p6.insert(0, music21.clef.TrebleClef())

# Mão direita: melodia fragmentada
fragmented_melody = [
    # C4 aparece 3x em sequência (deveria ser semínima pontuada + colcheia OU mínima + colcheia)
    ("C4", 0.5, 0.0),
    ("C4", 0.5, 0.5),
    ("C4", 0.5, 1.0),
    # E4 aparece 2x (deveria ser semínima)
    ("E4", 0.5, 1.5),
    ("E4", 0.5, 2.0),
    # G4 aparece 4x (deveria ser mínima)
    ("G4", 0.5, 2.5),
    ("G4", 0.5, 3.0),
    ("G4", 0.5, 3.5),
    ("G4", 0.5, 4.0),  # cruza barra em compasso 4/4 → deve manter 2 notas com tie ou fundir dependendo da posição
]

for pitch_str, ql, off in fragmented_melody:
    n = note.Note(pitch_str)
    n.quarterLength = ql
    p6.insert(off, n)

score6.insert(0, p6)

n_before = len(list(score6.flatten().getElementsByClass(['Note'])))
result6 = apply_musical_intelligence(score6, bpm=110.0, time_sig_str="4/4")
n_after = len(list(result6.flatten().getElementsByClass(['Note'])))

check(f"Pipeline completo: reduziu notas ({n_before} → {n_after})",
      n_after < n_before,
      f"{n_before - n_after} fusões")


# ===========================================================================
# TESTE 7: Detecção e regularização de padrões rítmicos
# ===========================================================================
print("\n" + "="*60)
print("TESTE 7 — Regularização de Padrões Rítmicos (Jitter)")
print("="*60)

# Compasso 1: ritmo exato (colcheia, semicolcheia, semicolcheia, mínima pontuada) = 0.5 + 0.25 + 0.25 + 3.0
# Compasso 2: jitter (com offsets imperfeitos e durações imperfeitas, mas mesmo # de notas)
score7 = make_score([
    # Compasso 1 (molde perfeito) - deslocado 0.0, 0.5, 0.75, 1.0 (soma=4.0)
    ("C4", 0.5, 0.0),
    ("D4", 0.25, 0.5),
    ("E4", 0.25, 0.75),
    ("F4", 3.0, 1.0),
    
    # Compasso 2 (com jitter nas durações e offsets, simulando erro da IA)
    # Offsets nominais no compasso 2 (inicio 4.0): 4.0, 4.5, 4.75, 5.0
    ("C4", 0.45, 4.05),   # atrasado 0.05, menor
    ("D4", 0.30, 4.45),   # adiantado 0.05, maior
    ("E4", 0.20, 4.80),   # atrasado 0.05, menor
    ("F4", 3.10, 4.95),   # adiantado 0.05, maior
], bpm=120.0)

# Verifica que o compasso 2 está bagunçado antes
notes7_before = list(score7.flatten().getElementsByClass(['Note']))
offsets_m2_before = [n.offset for n in notes7_before[4:]]
durations_m2_before = [n.quarterLength for n in notes7_before[4:]]
check("Antes da regularização: Offsets do compasso 2 têm jitter", offsets_m2_before != [4.0, 4.5, 4.75, 5.0], f"{offsets_m2_before}")

# Aplica correção de padrões
result7 = quantize_by_pattern(score7, time_sig_str="4/4", similarity_threshold=0.25)
notes7_after = list(result7.flatten().getElementsByClass(['Note']))
offsets_m2_after = [n.offset for n in notes7_after[4:]]
durations_m2_after = [n.quarterLength for n in notes7_after[4:]]

check("Após a regularização: Offsets do compasso 2 estão cravados", offsets_m2_after == [4.0, 4.5, 4.75, 5.0], f"{offsets_m2_after}")
check("Após a regularização: Durações do compasso 2 estão cravadas", durations_m2_after == [0.5, 0.25, 0.25, 3.0], f"{durations_m2_after}")


# ===========================================================================
# EXPORTA RESULTADO VISUAL
# ===========================================================================
print("\n" + "="*60)
print("EXPORTANDO RESULTADO VISUAL")
print("="*60)

try:
    # Adiciona compasso e cria medidas para visualização
    ts = meter.TimeSignature("4/4")
    for p in result6.parts:
        p.insert(0, ts)
    result6.makeMeasures(inPlace=True)
    result6.makeNotation(inPlace=True)

    out_path = os.path.join(os.path.dirname(__file__), "test_music_intelligence_out.musicxml")
    result6.write("musicxml", fp=out_path)
    print(f"Escrito: {out_path}")
    print("Abra no MuseScore ou Flat.io para verificar visualmente.")
except Exception as e:
    import traceback
    print(f"{WARN}Exportação falhou: {e}")
    traceback.print_exc()


# ===========================================================================
# RESUMO
# ===========================================================================
print("\n" + "="*60)
print("RESUMO DOS TESTES")
print("="*60)

total = len(results)
passed = sum(results)
failed = total - passed

print(f"  Passaram: {passed}/{total}")
if failed:
    print(f"  Falharam: {failed}/{total}")
    sys.exit(1)
else:
    print("  ✓ Todos os testes passaram!")
    sys.exit(0)
