from utils.MACROS import CLEANED_OFFERS_PATH
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid
import pandas as pd
from utils.MACROS import OFFER_COLUMNS
from utils.Offer import Offer



def _norm_link(link: Any) -> str:
    return str(link).strip().lower()


def _offer_to_row(o: Offer) -> Dict[str, Any]:
    return {
        "id": str(o.id) if o.id else None,
        "link": o.link,
        "reception_date": o.reception_date,
        "father_mail_subject": o.father_mail_subject,
        "affinity": o.affinity,
        "description": o.description[:20],
    }


def _load_offers_from_excel(
    excel_path: str | Path,
    sheet_name: str | int = 0,
) -> List[Offer]:
    """
    Lee un Excel cuyas columnas corresponden a TODOS los campos de Offer:
    id, link, reception_date, father_mail_subject, affinity, description

    Retorna List[Offer].
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {excel_path}")

    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # Validación: deben existir todas las columnas del modelo
    missing = [c for c in OFFER_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas en el Excel: {missing}. "
            f"Columnas encontradas: {list(df.columns)}"
        )

    offers: List[Offer] = []

    for _, row in df.iterrows():
        # Constructor requiere estas 3
        link = row["link"]
        rdate = row["reception_date"]
        subject = row["father_mail_subject"]

        # si faltan datos básicos, ignora la fila
        if pd.isna(link) or pd.isna(rdate) or pd.isna(subject):
            print("Ignorando fila al leer el sheets")
            continue

        o = Offer(str(link).strip(), rdate, str(subject))

        # id (obligatorio como columna, pero puede venir vacío)
        raw_id = row["id"]
        if raw_id is not None and not pd.isna(raw_id):
            try:
                o.id = uuid.UUID(str(raw_id))
            except Exception:
                # si no es UUID válido, se queda el generado
                pass

        # affinity (columna obligatoria, puede venir vacía)
        raw_aff = row["affinity"]
        o.affinity = None if raw_aff is None or pd.isna(raw_aff) else raw_aff

        # description (columna obligatoria, puede venir vacía)
        raw_desc = row["description"]
        o.description = None if raw_desc is None or pd.isna(raw_desc) else str(raw_desc)

        offers.append(o)

    return offers



def _merge_offers_dedup_by_link(
    list_a: List[Offer],
    list_b: List[Offer],
    keep: str = "first",  # "first" => prioriza A, "last" => prioriza B
) -> List[Offer]:
    """
    Fusiona list_a + list_b, detecta links duplicados y elimina una de las duplicadas.

    keep="first": conserva la primera aparición (prioriza list_a).
    keep="last": conserva la última aparición (prioriza list_b).
    """
    if keep not in {"first", "last"}:
        raise ValueError("keep debe ser 'first' o 'last'.")

    merged = list_a + list_b

    if keep == "first":
        seen = set()
        out: List[Offer] = []
        for o in merged:
            if not o.link:
                continue
            k = _norm_link(o.link)
            if k in seen:
                continue
            seen.add(k)
            out.append(o)
        return out

    # keep == "last"
    by_link: Dict[str, Offer] = {}
    order: List[str] = []
    for o in merged:
        if not o.link:
            continue
        k = _norm_link(o.link)
        if k not in by_link:
            order.append(k)
        by_link[k] = o
    return [by_link[k] for k in order]

def _write_offers_to_excel(
    offers: List[Offer],
    excel_path: str | Path,
    sheet_name: str = "offers",
) -> None:
    """
    Escribe (sobrescribe) un Excel con TODAS las columnas del modelo Offer:
    id, link, reception_date, father_mail_subject, affinity, description
    """
    excel_path = Path(excel_path)

    df = pd.DataFrame([_offer_to_row(o) for o in offers], columns=OFFER_COLUMNS)

    # Sobrescribe el archivo completo (simple y seguro)
    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="w") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)


def writing_handler(offers_list, PATH=CLEANED_OFFERS_PATH):
    """
        Funcion encargada de:

        1. Cargar offers anteriores
        2. Fusionarlas con las nuevas
        3. Eliminar duplicados
        4. Escribir final en archivo
    """

    print("Cargando ofertas antiguas")

    old_offers = _load_offers_from_excel(PATH)
    print(f"Se cargaron {len(old_offers)} ofertas")


    print("Fusionando ofertas viejas con las nuevas")
    print(f"Ofertas nuevas : {len(offers_list)}")
    print(f"Ofertas viejas : {len(old_offers)}")
    final_offers = _merge_offers_dedup_by_link(offers_list, old_offers)
    print(f"Ofertas finales : {len(final_offers)}")

    print("Escribiendo ofertas finales en sheets")
    _write_offers_to_excel(final_offers,PATH)
