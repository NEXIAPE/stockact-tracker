"""
Capa de consolidación.

Toma divulgaciones provenientes de uno o varios conectores y produce un
conjunto limpio:

  1. Deduplicación EXACTA: dos registros que describen la misma operación
     económica (misma ``transaction_key``) se colapsan en uno.
  2. Resolución de enmiendas: una enmienda (``is_amendment = True`` con
     ``amends_doc_id``) reemplaza la transacción original del filing que
     corrige. Así el informe refleja el dato más reciente, no el erróneo.

Devuelve la lista consolidada y estadísticas (``duplicates_removed`` y
``amendments_merged``) que el --self-test verifica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from models import Disclosure


@dataclass
class ConsolidationStats:
    input_count: int = 0
    output_count: int = 0
    duplicates_removed: int = 0
    amendments_merged: int = 0


def consolidate(disclosures: List[Disclosure]) -> Tuple[List[Disclosure], ConsolidationStats]:
    stats = ConsolidationStats(input_count=len(disclosures))

    # --- 1. Deduplicación exacta -------------------------------------------
    seen: dict[str, Disclosure] = {}
    deduped: List[Disclosure] = []
    for d in disclosures:
        key = d.transaction_key()
        if key in seen:
            stats.duplicates_removed += 1
            continue
        seen[key] = d
        deduped.append(d)

    # --- 2. Resolución de enmiendas ----------------------------------------
    originals = [d for d in deduped if not d.is_amendment]
    amendments = [d for d in deduped if d.is_amendment]

    result: List[Disclosure] = list(originals)
    for amd in amendments:
        replaced = False
        for i, orig in enumerate(result):
            if orig.is_amendment:
                continue
            # La enmienda apunta al filing original (amends_doc_id) y coincide
            # el sujeto (legislador + activo).
            if (
                amd.amends_doc_id
                and orig.doc_id == amd.amends_doc_id
                and amd.amendment_subject_key() == orig.amendment_subject_key()
            ):
                result[i] = amd
                stats.amendments_merged += 1
                replaced = True
                break
        if not replaced:
            # Enmienda sin original localizable: se conserva como registro
            # propio para no perder información.
            result.append(amd)

    stats.output_count = len(result)
    return result, stats
