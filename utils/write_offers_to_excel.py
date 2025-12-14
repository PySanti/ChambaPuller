from utils.MACROS import CLEANED_OFFERS_PATH
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from utils.MACROS import OFFER_COLUMNS
from utils.Offer import Offer



def _norm_link(link: Any) -> str:
    return str(link).strip().lower()


def _offer_to_row(o: Offer) -> Dict[str, Any]:
    return {
        "id": str(o.id) if o.id else None,
        "link": o.link,
        "reception_date": str(o.reception_date),
        "father_mail_subject": o.father_mail_subject,
        "affinity": o.affinity,
        "description": o.description[:20],
    }


def write_offers_to_excel(
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

