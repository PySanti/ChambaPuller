from utils.MACROS import OFFER_BATCH_SIZE
from utils.gemini_query import gemini_query
from utils.generate_prompt import generate_prompt


def _get_offer_batch_affinity(offers):
    """
        Hara la consulta a gemini enviando batches de ofertas para aprovechar mejor
        los limites impuestos por gemini

        Gemini respondera con el siguiente formato :
            uuid-calificacion;uudi-calificacion...

        Retorna la respuesta de gemini
    """
    prompt = generate_prompt(offers)
    gemini_response = gemini_query(prompt)
    return gemini_response

def _set_offer_batch_affinity_by_gemini_response(gemini_response, offers_list):
    """
        Recibe respuesta de gemini con el siguiente formato:
            uuid-calificacion;uudi-calificacion...

        Y ajusta la afinidad de cada oferta correspondiente.

    """
    i = 0
    for calification_pairs in gemini_response.split(';'):
        uuid, calification = calification_pairs.split('_')
        for o in offers_list:
            if str(o.id) == uuid:
                print(f"Asignando afinidad de oferta : {o.id}")
                i +=1
                o.affinity = int(calification)




def offer_list_affinity_handler(offers_list, batch_size=OFFER_BATCH_SIZE):
    """
        Se encarga de tomar toda la lista de ofertas y ajustar su afinidad
        por batches cuyo tamanio esta determinado por OFFER_BATCH_SIZE
    """
    i = 0
    offer_batch = None
    while i != -1:
        if (len(offers_list)-i) < batch_size:
            offer_batch = offers_list[i:]
            i = -1
        else:
            offer_batch = offers_list[i:i+batch_size]
            i+=batch_size
        print(f"Enviando {len(offer_batch)} ofertas a gemini para encontrar su afinidad")
        gemini_response = _get_offer_batch_affinity(offer_batch)
        _set_offer_batch_affinity_by_gemini_response(gemini_response, offer_batch)

