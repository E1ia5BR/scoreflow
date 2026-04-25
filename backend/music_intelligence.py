"""
music_intelligence.py
=====================
Módulo de pós-processamento musical que transforma a saída bruta da IA em
uma partitura musicalmente inteligente e legível.

O que este módulo faz
---------------------
A IA (Magenta/Basic Pitch) gera notas com durações baseadas em ms de áudio,
não em figuras musicais reais. O resultado são fragmentos que deveriam ser
escritos como figuras maiores (ex: duas semínimas de C4 → mínima de C4).

Este módulo implementa 4 etapas em sequência:

  1. choose_rhythmic_grid(bpm, time_sig)
     → Escolhe a grade rítmica adequada para aquele andamento.
     Ex: BPM 180 → grade de colcheias/semínimas; BPM 60 → semicolcheias.

  2. snap_to_musical_grid(score, grid)
     → Re-quantiza as notas usando a grade escolhida (substitui a grade
     fixa (4,8,16) que temos hoje).

  3. defragment_rhythms(score, time_sig, bpm)
     → Coração do módulo: percorre a partitura e funde figuras consecutivas
     do mesmo pitch em figuras maiores (desfragmentação rítmica).
     - Duas semínimas de C4 → mínima de C4
     - Semínima + colcheia de C4 → semínima pontuada de C4
     - Quatro colcheias de C4 → mínima de C4
     Respeita as barras de compasso: fusões que cruzariam barras ficam com
     ligadura de prolongamento (tie).

  4. apply_musical_intelligence(score, bpm, time_sig_str)
     → Função de entrada que orquestra as 3 etapas acima.
"""

from __future__ import annotations

import copy
import math
from typing import List, Tuple

import music21
from music21 import note, chord, stream, meter, tempo as m21tempo


# ---------------------------------------------------------------------------
# FIGURAS RÍTMICAS CANÔNICAS (em quarter-lengths)
# ---------------------------------------------------------------------------
# Estas são as figuras padrão que um compositor/arranjador usa.
# A fusão sempre tentará gerar figuras desta lista.

CANONICAL_DURATIONS_QL = [
    4.0,   # semibreve
    3.0,   # mínima pontuada
    2.0,   # mínima
    1.5,   # semínima pontuada
    1.0,   # semínima
    0.75,  # colcheia pontuada
    0.5,   # colcheia
    0.375, # semicolcheia pontuada
    0.25,  # semicolcheia
    0.125, # fusa
]


# ---------------------------------------------------------------------------
# 1. GRADE RÍTMICA ADAPTATIVA
# ---------------------------------------------------------------------------

def choose_rhythmic_grid(bpm: float, time_sig_str: str = "4/4") -> Tuple[int, ...]:
    """
    Escolhe a menor figura rítmica válida dado o andamento e o compasso.

    O princípio musical: em andamentos rápidos, figuras muito curtas
    (semicolcheias/fusas) seriam inaudíveis/ininterpretáveis. A grade
    deve refletir o que é *executável* naquele andamento.

    Parâmetros
    ----------
    bpm          : Andamento em BPM. Se 0 ou None, usa 120 como padrão.
    time_sig_str : Compasso (ex: "4/4", "3/4", "6/8").

    Retorna
    -------
    Tupla de denominadores de grade para music21.quantize, ex:
    (4, 8) = semínimas + colcheias
    (4, 8, 16) = semínimas + colcheias + semicolcheias
    """
    if not bpm or bpm <= 0:
        bpm = 120.0

    # Duração de uma semicolcheia em ms
    ms_per_beat = 60000.0 / bpm
    ms_per_sixteenth = ms_per_beat / 4.0

    try:
        ts = meter.TimeSignature(time_sig_str)
        denominator = ts.denominator
    except Exception:
        denominator = 4

    # Lógica de grade por andamento:
    # Muito rápido (>160 BPM): semicolcheias são difíceis; usar semínima+colcheia
    # Rápido (120-160 BPM): colcheias e semicolcheias
    # Médio (80-120 BPM): colcheias e semicolcheias (padrão)
    # Lento (<80 BPM): semicolcheias e fusas permitidas

    if bpm > 160:
        grid = (4, 8)           # semínima + colcheia (figuras mais longas)
    elif bpm > 100:
        grid = (4, 8, 16)      # padrão: semínima + colcheia + semicolcheia
    elif bpm > 60:
        grid = (4, 8, 16)      # padrão
    else:
        grid = (4, 8, 16, 32)  # lento: inclui fusas

    # Ajuste para compassos compostos (6/8, 9/8, 12/8):
    # A unidade de tempo é a colcheia, então a grade começa em 8
    if denominator == 8:
        grid = tuple(g * 2 for g in grid if g * 2 <= 32)
        if not grid:
            grid = (8, 16)

    print(f"[music_intelligence] BPM={bpm:.1f} → grade rítmica: {grid}", flush=True)
    return grid


# ---------------------------------------------------------------------------
# 2. RE-QUANTIZAÇÃO COM GRADE ADAPTATIVA
# ---------------------------------------------------------------------------

def snap_to_musical_grid(
    score: music21.stream.Score,
    grid: Tuple[int, ...],
) -> music21.stream.Score:
    """
    Quantiza o score usando a grade rítmica escolhida por choose_rhythmic_grid.

    Parâmetros
    ----------
    score : Score music21 já limpo (sem ghost notes).
    grid  : Tupla de denominadores, ex: (4, 8, 16).

    Retorna
    -------
    Novo Score com offsets e durações quantizados.
    """
    new_score = music21.stream.Score()

    # Copia elementos de nível superior (tempo, metadados)
    for el in score.getElementsByClass(['MetronomeMark', 'Metadata']):
        new_score.insert(el.offset, copy.deepcopy(el))

    for part in score.parts:
        new_part = music21.stream.Part()

        # Copia clef/key/time sig
        for el in part.flat.getElementsByClass(['Clef', 'KeySignature', 'TimeSignature', 'MetronomeMark']):
            new_part.insert(el.offset, copy.deepcopy(el))

        # Copia todas as notas/acordes
        for el in part.flat.getElementsByClass(['Note', 'Chord']):
            new_part.insert(el.offset, copy.deepcopy(el))

        # Aplica quantização com a grade adaptativa
        try:
            new_part.quantize(grid, processOffsets=True, processDurations=True, inPlace=True)
        except Exception as e:
            print(f"[music_intelligence] Aviso: quantize falhou ({e}), mantendo original", flush=True)

        new_score.insert(0, new_part)

    return new_score


# ---------------------------------------------------------------------------
# 3. DESFRAGMENTAÇÃO RÍTMICA (coração do módulo)
# ---------------------------------------------------------------------------

def _nearest_canonical(ql: float, min_ql: float = 0.125) -> float:
    """Retorna a figura canônica mais próxima de 'ql' que seja >= min_ql."""
    candidates = [d for d in CANONICAL_DURATIONS_QL if d >= min_ql]
    if not candidates:
        return ql
    return min(candidates, key=lambda d: abs(d - ql))


def _notes_are_same_pitch(a: music21.base.Music21Object, b: music21.base.Music21Object) -> bool:
    """
    Retorna True se 'a' e 'b' têm exatamente o mesmo pitch (ou pitches, para acordes).
    """
    try:
        if type(a) != type(b):
            return False
        if isinstance(a, note.Note) and isinstance(b, note.Note):
            return a.pitch.midi == b.pitch.midi
        if isinstance(a, chord.Chord) and isinstance(b, chord.Chord):
            if len(a.pitches) != len(b.pitches):
                return False
            return all(p1.midi == p2.midi for p1, p2 in zip(
                sorted(a.pitches, key=lambda p: p.midi),
                sorted(b.pitches, key=lambda p: p.midi)
            ))
    except Exception:
        pass
    return False


def _defragment_part(
    elements: List[Tuple[float, music21.base.Music21Object]],
    bar_ql: float,
    min_figure_ql: float,
) -> List[Tuple[float, music21.base.Music21Object]]:
    """
    Percorre uma lista de (offset, elemento) e funde notas consecutivas
    do mesmo pitch em figuras maiores.

    Regras de fusão:
    - Notas/acordes consecutivos do *mesmo* pitch
    - Sem gap entre elas (offset_B == offset_A + duracao_A)
    - A fusão NÃO pode cruzar barra de compasso SEM ligadura
    - A duração resultante deve ser uma figura canônica

    Parâmetros
    ----------
    elements    : Lista ordenada por offset de (offset, note/chord).
    bar_ql      : Duração de um compasso em quarter-lengths.
    min_figure_ql: Menor figura permitida (derivada da grade).

    Retorna
    -------
    Lista de (offset, elemento) com fusões aplicadas.
    """
    if not elements:
        return elements

    # Ordena por offset
    elements = sorted(elements, key=lambda x: x[0])

    result = []
    i = 0
    while i < len(elements):
        off_a, el_a = elements[i]
        merged_ql = el_a.quarterLength
        j = i + 1

        # Tenta fundir com os próximos elementos do mesmo pitch
        while j < len(elements):
            off_b, el_b = elements[j]

            # Há gap entre o fim de A e o início de B?
            end_a = off_a + merged_ql
            gap = abs(off_b - end_a)
            if gap > 0.01:  # tolerância de 1 centésimo de QL
                break

            # São do mesmo pitch?
            if not _notes_are_same_pitch(el_a, el_b):
                break

            # A fusão cruzaria uma barra de compasso?
            # Verifica se os dois pontos estão no mesmo compasso
            bar_a = math.floor(off_a / bar_ql)
            bar_b = math.floor((off_b + el_b.quarterLength - 0.001) / bar_ql)
            crosses_bar = (bar_b > bar_a)

            candidate_ql = merged_ql + el_b.quarterLength
            canonical = _nearest_canonical(candidate_ql, min_figure_ql)

            # Funde somente se a duração resultante for canônica (tolerância 0.05 QL)
            if abs(canonical - candidate_ql) > 0.05:
                break

            if crosses_bar:
                # Fusão entre compassos: usa tie
                # Não funde em uma nota só — a fusão com tie será tratada abaixo
                break

            # Tudo ok — funde!
            merged_ql = canonical
            j += 1

        # Cria o elemento fundido
        new_el = copy.deepcopy(el_a)
        new_el.quarterLength = merged_ql

        # Remove ties antigos (serão recriados pelo makeNotation)
        try:
            new_el.tie = None
        except Exception:
            pass

        result.append((off_a, new_el))
        i = j  # pula os elementos que foram fundidos

    return result


def defragment_rhythms(
    score: music21.stream.Score,
    time_sig_str: str = "4/4",
    bpm: float = 120.0,
    min_figure_ql: float = 0.25,
) -> music21.stream.Score:
    """
    Percorre o score e funde figuras rítmicas fragmentadas em figuras maiores.

    Por exemplo:
    - C4 semínima (1.0) + C4 semínima (1.0) → C4 mínima (2.0)
    - C4 semínima (1.0) + C4 colcheia (0.5) → C4 semínima pontuada (1.5)
    - C4 colcheia ×4 → C4 mínima (2.0)

    Parâmetros
    ----------
    score         : Score após quantização.
    time_sig_str  : Compasso para saber onde ficam as barras.
    bpm           : BPM para calcular min_figure_ql se não fornecido explicitamente.
    min_figure_ql : Menor figura que pode resultar da fusão.

    Retorna
    -------
    Novo Score com ritmos desfragmentados.
    """
    try:
        ts = meter.TimeSignature(time_sig_str)
        bar_ql = ts.barDuration.quarterLength
    except Exception:
        bar_ql = 4.0

    new_score = music21.stream.Score()

    # Mantém elementos de topo (tempo, metadados)
    for el in score.getElementsByClass(['MetronomeMark', 'Metadata']):
        new_score.insert(el.offset, copy.deepcopy(el))

    for part in score.parts:
        new_part = music21.stream.Part()

        # Copia clef/key/time sig
        for el in part.flat.getElementsByClass(['Clef', 'KeySignature', 'TimeSignature', 'MetronomeMark']):
            new_part.insert(el.offset, copy.deepcopy(el))

        # Coleta notas com offsets absolutos
        elements = []
        for el in part.flat.getElementsByClass(['Note', 'Chord']):
            elements.append((el.offset, copy.deepcopy(el)))

        # Aplica desfragmentação
        defragmented = _defragment_part(elements, bar_ql, min_figure_ql)

        # Conta quantas fusões ocorreram
        n_before = len(elements)
        n_after = len(defragmented)
        if n_before > n_after:
            print(
                f"[music_intelligence] Desfragmentação: {n_before} → {n_after} notas "
                f"({n_before - n_after} fusões aplicadas)",
                flush=True
            )

        # Insere os elementos fundidos na nova parte
        for off, el in defragmented:
            new_part.insert(off, el)

        new_score.insert(0, new_part)

    return new_score


# ---------------------------------------------------------------------------
# 4. SIMPLIFICAÇÃO DE NOTAÇÃO — remove ties desnecessários
# ---------------------------------------------------------------------------

def simplify_tied_notes(score: music21.stream.Score) -> music21.stream.Score:
    """
    Remove ties redundantes introduzidos pelo AI ou pelo processo de quantização
    quando a duração resultante já é uma figura canônica.

    Por exemplo:
    - Semínima (1.0) tie Semínima (1.0) → se ambas são C4, vira mínima (2.0)
    - Colcheia (0.5) tie Colcheia (0.5) → semínima (1.0)

    Esta função complementa defragment_rhythms trabalhando em notas que já
    têm ties explícitos no XML original.
    """
    new_score = music21.stream.Score()

    for el in score.getElementsByClass(['MetronomeMark', 'Metadata']):
        new_score.insert(el.offset, copy.deepcopy(el))

    for part in score.parts:
        new_part = music21.stream.Part()

        for el in part.flat.getElementsByClass(['Clef', 'KeySignature', 'TimeSignature', 'MetronomeMark']):
            new_part.insert(el.offset, copy.deepcopy(el))

        elements = list(part.flat.getElementsByClass(['Note', 'Chord']))
        skip_until = -1

        for idx, el in enumerate(elements):
            if idx <= skip_until:
                continue

            # Verifica se esta nota inicia uma cadeia de tie
            if (hasattr(el, 'tie') and el.tie is not None and
                    el.tie.type in ('start', 'continue')):
                # Coleta toda a cadeia de ties
                total_ql = el.quarterLength
                last_idx = idx
                k = idx + 1
                while k < len(elements):
                    next_el = elements[k]
                    if (_notes_are_same_pitch(el, next_el) and
                            hasattr(next_el, 'tie') and next_el.tie is not None and
                            next_el.tie.type in ('continue', 'stop')):
                        total_ql += next_el.quarterLength
                        last_idx = k
                        if next_el.tie.type == 'stop':
                            break
                        k += 1
                    else:
                        break

                # Verifica se a duração total é uma figura canônica
                canonical = _nearest_canonical(total_ql)
                if abs(canonical - total_ql) < 0.05:
                    # Funde em uma nota só
                    new_el = copy.deepcopy(el)
                    new_el.quarterLength = canonical
                    new_el.tie = None
                    new_part.insert(el.offset, new_el)
                    skip_until = last_idx
                    continue

            # Nota normal - copia como está
            new_part.insert(el.offset, copy.deepcopy(el))

        new_score.insert(0, new_part)

    return new_score


# ---------------------------------------------------------------------------
# 5. DETECÇÃO E REGULARIZAÇÃO DE PADRÕES RÍTMICOS
# ---------------------------------------------------------------------------

def quantize_by_pattern(
    score: music21.stream.Score,
    time_sig_str: str = "4/4",
    similarity_threshold: float = 0.25,
) -> music21.stream.Score:
    """
    Identifica padrões rítmicos repetidos entre compassos consecutivos da melodia.
    Se um compasso N tiver o mesmo número de elementos e um ritmo quase idêntico
    ao compasso N-1, ele "copia" a estrutura rítmica exata do compasso N-1.
    Isso remove o "jitter" da transcrição da IA.
    """
    try:
        ts = meter.TimeSignature(time_sig_str)
        bar_ql = ts.barDuration.quarterLength
    except Exception:
        bar_ql = 4.0

    new_score = music21.stream.Score()
    
    for el in score.getElementsByClass(['MetronomeMark', 'Metadata']):
        new_score.insert(el.offset, copy.deepcopy(el))

    for part in score.parts:
        new_part = music21.stream.Part()
        for el in part.flat.getElementsByClass(['Clef', 'KeySignature', 'TimeSignature', 'MetronomeMark']):
            new_part.insert(el.offset, copy.deepcopy(el))
            
        elements = list(part.flat.getElementsByClass(['Note', 'Chord']))
        if not elements:
            new_score.insert(0, new_part)
            continue
            
        # Agrupa elementos por compasso "virtual" (baseado em bar_ql)
        measures = {}
        for el in elements:
            bar_idx = math.floor((el.offset + 0.001) / bar_ql)
            if bar_idx not in measures:
                measures[bar_idx] = []
            el_copy = copy.deepcopy(el)
            # Ao fazer deepcopy de elemento do .flat, ele perde o contexto e o offset vira 0.0
            # Precisamos forçar o offset absoluto.
            el_copy.offset = float(el.offset)
            measures[bar_idx].append(el_copy)
            
        sorted_bars = sorted(measures.keys())
        processed_elements = []
        
        prev_bar_idx = None
        prev_m_elements = None
        num_patterns_fixed = 0
        
        for bar_idx in sorted_bars:
            m_elements = measures[bar_idx]
            m_elements.sort(key=lambda x: x.offset)
            
            # Se não houver compasso anterior direto para comparar
            if prev_bar_idx is None or prev_bar_idx != bar_idx - 1:
                prev_bar_idx = bar_idx
                prev_m_elements = copy.deepcopy(m_elements)
                processed_elements.extend(m_elements)
                continue
                
            # Verifica similaridade 
            if len(m_elements) == len(prev_m_elements) and len(m_elements) > 0:
                is_similar = True
                
                for i in range(len(m_elements)):
                    el_curr = m_elements[i]
                    el_prev = prev_m_elements[i]
                    
                    rel_off_curr = float(el_curr.offset) - (bar_idx * bar_ql)
                    rel_off_prev = float(el_prev.offset) - (prev_bar_idx * bar_ql)
                    
                    diff_off = abs(rel_off_curr - rel_off_prev)
                    diff_dur = abs(float(el_curr.quarterLength) - float(el_prev.quarterLength))
                    
                    if diff_off > similarity_threshold or diff_dur > similarity_threshold:
                        is_similar = False
                        break
                        
                if is_similar:
                    for i in range(len(m_elements)):
                        el_curr = m_elements[i]
                        el_prev = prev_m_elements[i]
                        # Precisamos redefinir a duração do elemento!
                        el_curr.quarterLength = float(el_prev.quarterLength)
                        # O offset nominal que este elemento deveria ter
                        el_curr.offset = float(el_prev.offset) + bar_ql
                    num_patterns_fixed += 1
                    
            prev_bar_idx = bar_idx
            prev_m_elements = copy.deepcopy(m_elements)
            processed_elements.extend(m_elements)
            
        if num_patterns_fixed > 0:
            print(f"[music_intelligence] Padrões rítmicos regulados: {num_patterns_fixed} compassos assumiram ritmo anterior.", flush=True)
            
        for el in processed_elements:
            new_part.insert(float(el.offset), el)
            
        new_score.insert(0, new_part)
        
    return new_score

# ---------------------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE ENTRADA
# ---------------------------------------------------------------------------

def apply_musical_intelligence(
    score: music21.stream.Score,
    bpm: float,
    time_sig_str: str = "4/4",
) -> music21.stream.Score:
    """
    Aplica inteligência musical ao score gerado pela IA.

    Etapas executadas em sequência:
    1. Grade rítmica adaptativa ao andamento
    2. Re-quantização com a grade escolhida
    3. Desfragmentação rítmica (fusão de figuras)
    4. Simplificação de ties redundantes
    5. Padronização de ritmos oscilantes

    Parâmetros
    ----------
    score        : Score após clean_and_quantize_score (pipeline existente).
    bpm          : BPM detectado do áudio.
    time_sig_str : Compasso escolhido pelo usuário.

    Retorna
    -------
    Score aprimorado musicalmente.
    """
    if not bpm or bpm <= 0:
        bpm = 120.0

    print(f"[music_intelligence] Iniciando — BPM={bpm:.1f}, compasso={time_sig_str}", flush=True)

    # Contar notas antes para log
    n_before = len(list(score.flatten().getElementsByClass(['Note', 'Chord'])))
    print(f"[music_intelligence] Notas antes: {n_before}", flush=True)

    # --- Passo 1: Grade rítmica adaptativa ---
    grid = choose_rhythmic_grid(bpm, time_sig_str)

    # --- Passo 2: Re-quantização com grade adaptativa ---
    score = snap_to_musical_grid(score, grid)

    # Determina a menor figura possível com a grade escolhida
    # (ex: grade (4,8) → menor figura = colcheia = 0.5 QL)
    min_denominator = max(grid)
    min_figure_ql = 4.0 / min_denominator  # 4/8 = 0.5 QL, 4/16 = 0.25 QL

    # --- Passo 3: Desfragmentação rítmica ---
    score = defragment_rhythms(score, time_sig_str, bpm, min_figure_ql)

    # --- Passo 4: Simplificação de ties ---
    score = simplify_tied_notes(score)

    # --- Passo 5: Detecção de padrões repetidos ---
    # Realiza um smooth para o jitter entre medidas que pretendiam ser iguais.
    score = quantize_by_pattern(score, time_sig_str)

    # Log final
    n_after = len(list(score.flatten().getElementsByClass(['Note', 'Chord'])))
    print(
        f"[music_intelligence] Concluído — {n_before} → {n_after} notas "
        f"({n_before - n_after} figuras fundidas no total)",
        flush=True
    )

    return score
