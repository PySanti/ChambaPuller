from utils.get_last_offers import get_last_offers
from utils.get_offer_description import get_offer_description
from time import sleep


# PIPELINE PRINCIPAL

if __name__ == "__main__":
    # Se cargan todas las ofertas de los ultimos N correos relacionados con ofertas de trabajo
    last_offers = get_last_offers(limit=10)


    # De recorren todas las ofertas y para cada una
    for offer in last_offers:
        print(f"Oferta recibida en mail : {offer.father_mail_subject}")

        # Se accede a linkedin, se extrae la description de la oferta y se setea
        offer.set_description()
        print(offer.description)
        sleep(5)
    

