from google.genai.types import CompletionStatsOrDict
from utils.MACROS import CLEANED_OFFERS_PATH
from utils.get_last_offers import get_last_offers
from time import sleep
from typing import List
from utils.Offer import Offer
from utils.load_offers_from_excel import load_offers_from_excel
from utils.offer_filter_handler import offer_filter_handler
from utils.remove_duplicated_offers import remove_duplicated_offers
from utils.write_offers_to_excel import write_offers_to_excel
from utils.offer_list_affinity_handler import offer_list_affinity_handler


# PIPELINE PRINCIPAL

if __name__ == "__main__":
    # Se cargan las ofertas contenidas en el excel
    print("Cargando ofertas antiguas")
    old_offers = load_offers_from_excel(CLEANED_OFFERS_PATH)
    print(f"Se cargaron {len(old_offers)} ofertas viejas")

    # Se cargan todas las ofertas de los ultimos N correos relacionados con ofertas de trabajo
    N = 300
    print(f"Cargando ofertas de los ultimos {N} correos")
    offers_list : List[Offer] = get_last_offers(limit=N) 
    print(f"Ofertas nuevas detectadas : {len(offers_list)}")

    print("Fusionando ofertas")
    total_offers = old_offers + offers_list
    print("Limpiando duplicados entre ofertas viejas y nuevas")
    cleaned_total_offers = remove_duplicated_offers(total_offers)
    print(f"Se encontraron {len(total_offers)-len(cleaned_total_offers)} duplicados")


    # Se recorren todas las ofertas y para cada una
    for offer in cleaned_total_offers:
        if not offer.description:
            try:
                # Se accede a linkedin, se extrae la description de la oferta y se setea
                offer.set_description()
                print(f"Se ajusto la descripcion de la oferta : {offer.link}")
            except:
                print(f"ERROR al tratar de ajustar la descripcion de : {offer.link}")
            sleep(5)
        else:
            print(f"Saltando oferta {offer.link} por que ya cuenta con descripcion")

    # Se eliminan las ofertas cuya descripcion no pudo ser encontrada
    cleaned_total_offers = offer_filter_handler(cleaned_total_offers)

    # Luego de cargar todas las descripciones de todas las ofertas, enviamos prompts a gemini en batches de 10 en 10

    print("Empezando a generar afinidad para cada oferta")
    offer_list_affinity_handler(cleaned_total_offers)
   
    print(f"Guardando {len(cleaned_total_offers)} en el excel")
    write_offers_to_excel(cleaned_total_offers, CLEANED_OFFERS_PATH)

    print("Fin del pipeline ...")
