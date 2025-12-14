from utils.Offer import Offer

def offer_filter_handler(offers: list[Offer]) -> list[Offer]:
    """
    Retorna una nueva lista con solo las ofertas que tienen description.
    
    :param offers: Lista de objetos Offer
    :return: Lista filtrada de objetos Offer con description no nula
    """
    print("Eliminando ofertas sin description")
    new_offer_list = [offer for offer in offers if offer.description is not None]
    print(f"Se eliminaron {len(offers)-len(new_offer_list)} ofertas")
    return new_offer_list
