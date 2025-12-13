from utils.MACROS import OFFER_BATCH_SIZE
from utils.get_last_offers import get_last_offers
from time import sleep

from utils.get_offers_affinity import get_offers_affinity
from utils.load_offers_batches import load_offers_batches


# PIPELINE PRINCIPAL

if __name__ == "__main__":
    # Se cargan todas las ofertas de los ultimos N correos relacionados con ofertas de trabajo
    N = 10
    print(f"Cargando ofertas de los ultimos {N} correos")
    last_offers = get_last_offers(limit=N)

    print(f"Ofertas detectadas : {len(last_offers)}")

    # De recorren todas las ofertas y para cada una
    for offer in last_offers:
        print(f"Accediento a Linkedin para buscar descripcion de oferta : {offer.link}")

        # Se accede a linkedin, se extrae la description de la oferta y se setea
        offer.set_description()
        sleep(5)
    print("Descripciones encontradas para todas las ofertas")

    print("Empezando a generar afinidad para cada oferta")

    # Luego de cargar todas las descripciones de todas las ofertas, enviamos prompts a gemini en batches de 10 en 10
    load_offers_batches(last_offers)

    for o in last_offers:
        print(o)
