from utils.MACROS import OFFER_BATCH_SIZE
from utils.get_offers_affinity import get_offers_affinity

def load_offers_batches(offers_list):
    i = 0
    offer_batch = None
    while i != -1:
        if (len(offers_list)-i) < OFFER_BATCH_SIZE:
            offer_batch = offers_list[i:]
            i = -1
        else:
            offer_batch = offers_list[i:i+10]
            i+=10
        print(f"Enviando {len(offer_batch)} ofertas a gemini para encontrar su afinidad")
        get_offers_affinity(offer_batch)


