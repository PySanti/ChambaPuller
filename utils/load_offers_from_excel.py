from pathlib import Path
from typing import List
import pandas as pd
from utils.MACROS import OFFER_COLUMNS
from utils.Offer import Offer


def load_offers_from_excel(
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

        # affinity (columna obligatoria, puede venir vacía)
        raw_aff = row["affinity"]
        o.affinity = None if raw_aff is None or pd.isna(raw_aff) else raw_aff

        # description (columna obligatoria, puede venir vacía)
        raw_desc = row["description"]
        o.description = None if raw_desc is None or pd.isna(raw_desc) else str(raw_desc)

        offers.append(o)

    return offers



