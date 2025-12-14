from utils.get_last_offers import get_last_offers
from time import sleep
from typing import List
from utils.Offer import Offer
from utils.writing_handler import writing_handler


# PIPELINE PRINCIPAL

if __name__ == "__main__":
    # Se cargan todas las ofertas de los ultimos N correos relacionados con ofertas de trabajo
    N = 3
    print(f"Cargando ofertas de los ultimos {N} correos")
    offers_list : List[Offer] = get_last_offers(limit=N) 

    print(f"Ofertas detectadas : {len(offers_list)}")

    # Se recorren todas las ofertas y para cada una
    for offer in offers_list:
        try:
            # Se accede a linkedin, se extrae la description de la oferta y se setea
            offer.set_description()
            print(f"Se ajusto la descripcion de la oferta : {offer.link}")
        except:
            print(f"ERROR al tratar de ajustar la descripcion de : {offer.link}")
        sleep(5)
    print("Empezando a generar afinidad para cada oferta")
    # Luego de cargar todas las descripciones de todas las ofertas, enviamos prompts a gemini en batches de 10 en 10
    #    offer_list_affinity_handler(offers_list)
    
    writing_handler(offers_list)

    print("Fin del pipeline ...")
