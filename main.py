#!/usr/bin/env python3
"""
Rastreador modular de divulgaciones STOCK Act (v1: solo Camara).

Tuberia:
    conectores -> consolidacion (dedup + enmiendas) -> persistencia (SQLite,
    deteccion incremental de novedades) -> informe diario en texto.

Modos:
    python main.py                 Ejecucion normal (conectores activos en vivo).
    python main.py --ingest-file X Procesa un XML local (formato Camara) por la
                                   tuberia completa y guarda/repite informe.
    python main.py --self-test     Valida el flujo OFFLINE con samples/sample_FD.xml
                                   (debe eliminar 1 duplicado y fusionar 1 enmienda).

El informe es DESCRIPTIVO: no da recomendaciones de inversion.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date
from typing import List

from models import Disclosure
from consolidation import consolidate
from storage import Storage, DEFAULT_DB
from report import build_report
from connectors import active_connectors
from connectors.house import HouseConnector


SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "samples", "sample_FD.xml")


# ---------------------------------------------------------------------------
# Recoleccion
# ---------------------------------------------------------------------------
def gather_live(year: int | None = None) -> List[Disclosure]:
    """Recolecta de todos los conectores ACTIVOS (House en v1)."""
    collected: List[Disclosure] = []
    for conn in active_connectors():
        try:
            items = conn.fetch(year) if conn.name == "house" else conn.fetch()
            con_ticker = sum(1 for d in items if d.ticker)
            print(f"  [{conn.name}] {len(items)} divulgaciones ({con_ticker} con ticker)")
            if items and con_ticker == 0:
                from connectors.house import INDEX_ONLY_NOTICE
                print(f"      AVISO: {INDEX_ONLY_NOTICE}")
            collected.extend(items)
        except NotImplementedError as exc:
            print(f"  [{conn.name}] fetch en vivo no implementado: {exc}")
        except Exception as exc:
            print(f"  [{conn.name}] fallo la descarga: {exc}")
    return collected


def ingest_file(path: str) -> List[Disclosure]:
    """Parsea un XML local con el conector de la Camara."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return HouseConnector().parse(raw)


# ---------------------------------------------------------------------------
# Tuberia comun
# ---------------------------------------------------------------------------
def run_pipeline(disclosures: List[Disclosure], db_path: str, today: date | None = None) -> str:
    consolidated, stats = consolidate(disclosures)
    print(
        f"  Consolidacion: {stats.input_count} -> {stats.output_count} "
        f"(duplicados eliminados: {stats.duplicates_removed}, "
        f"enmiendas fusionadas: {stats.amendments_merged})"
    )
    storage = Storage(db_path)
    try:
        new_items = storage.save_new(consolidated)
        print(f"  Novedades guardadas: {len(new_items)} (total en BD: {storage.total_count()})")
        report = build_report(storage, new_items, today=today)
    finally:
        storage.close()
    return report


def write_report(report: str) -> str:
    today = date.today().isoformat()
    out_path = f"informe_{today}.txt"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    return out_path


# ---------------------------------------------------------------------------
# Self-test (offline)
# ---------------------------------------------------------------------------
def self_test() -> int:
    print("== SELF-TEST (offline) ==")
    print(f"Sample: {SAMPLE_PATH}")

    disclosures = ingest_file(SAMPLE_PATH)
    print(f"  Parseadas {len(disclosures)} divulgaciones del sample.")

    consolidated, stats = consolidate(disclosures)
    print(
        f"  duplicados_eliminados={stats.duplicates_removed} "
        f"enmiendas_fusionadas={stats.amendments_merged} "
        f"salida={stats.output_count}"
    )

    ok = True

    if stats.duplicates_removed != 1:
        print(f"  FALLO: se esperaba 1 duplicado eliminado, hubo {stats.duplicates_removed}")
        ok = False
    else:
        print("  OK: 1 duplicado eliminado.")

    if stats.amendments_merged != 1:
        print(f"  FALLO: se esperaba 1 enmienda fusionada, hubo {stats.amendments_merged}")
        ok = False
    else:
        print("  OK: 1 enmienda fusionada.")

    # Verifica que la enmienda efectivamente reemplazo el monto original de AAPL.
    aapl = [d for d in consolidated if d.ticker == "AAPL"]
    if len(aapl) != 1:
        print(f"  FALLO: se esperaba 1 registro AAPL tras fusion, hubo {len(aapl)}")
        ok = False
    elif aapl[0].amount_range != "$15,001 - $50,000":
        print(f"  FALLO: AAPL deberia reflejar el monto enmendado, tiene '{aapl[0].amount_range}'")
        ok = False
    else:
        print("  OK: AAPL refleja el monto enmendado ($15,001 - $50,000).")

    # Recorre persistencia + informe en una BD temporal (sin ensuciar el repo).
    tmp_db = tempfile.NamedTemporaryFile(prefix="selftest_", suffix=".db", delete=False)
    tmp_db.close()
    try:
        storage = Storage(tmp_db.name)
        new_items = storage.save_new(consolidated)
        # Ventana de informe anclada a las fechas del sample (mayo 2024).
        report = build_report(storage, new_items, today=date(2024, 5, 31))
        storage.close()
        if len(new_items) != stats.output_count:
            print(f"  FALLO: novedades guardadas {len(new_items)} != salida {stats.output_count}")
            ok = False
        else:
            print(f"  OK: {len(new_items)} novedades persistidas e informe generado.")
        # Re-ejecucion: deteccion incremental no debe encontrar novedades.
        storage2 = Storage(tmp_db.name)
        again = storage2.save_new(consolidated)
        storage2.close()
        if again:
            print(f"  FALLO: 2da ejecucion deberia dar 0 novedades, dio {len(again)}")
            ok = False
        else:
            print("  OK: deteccion incremental no repite novedades en 2da ejecucion.")
        if "NO es asesoramiento" not in report:
            print("  FALLO: el informe debe declarar que es descriptivo (sin recomendaciones).")
            ok = False
        else:
            print("  OK: informe descriptivo (declara que no es asesoramiento/recomendacion).")
    finally:
        os.unlink(tmp_db.name)

    print("== RESULTADO:", "EXITO ✅" if ok else "FALLO ❌", "==")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rastreador modular STOCK Act (v1: Camara).")
    parser.add_argument("--self-test", action="store_true", help="Valida el flujo offline.")
    parser.add_argument("--ingest-file", metavar="XML", help="Procesa un XML local (formato Camara).")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"Ruta de la BD SQLite (def: {DEFAULT_DB}).")
    parser.add_argument("--year", type=int, help="Anio del indice de la Camara a descargar (def: el actual).")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.ingest_file:
        print(f"== INGESTA DE ARCHIVO: {args.ingest_file} ==")
        disclosures = ingest_file(args.ingest_file)
    else:
        print("== EJECUCION EN VIVO (conectores activos) ==")
        disclosures = gather_live(args.year)

    report = run_pipeline(disclosures, args.db)
    out_path = write_report(report)
    print(f"\nInforme escrito en: {out_path}\n")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
