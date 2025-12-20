from utils.MACROS import OFFER_BATCH_SIZE
from utils.gemini_query import gemini_query
from utils.generate_prompt import generate_prompt
from utils.logging import success, error


def _get_offer_batch_affinity(offers):
    """
        Hara la consulta a gemini enviando batches de ofertas para aprovechar mejor
        los limites impuestos por gemini

        Gemini respondera con el siguiente formato :
            id-calificacion;di-calificacion...

        Retorna la respuesta de gemini
    """
    prompt = generate_prompt(offers)
    gemini_response = gemini_query(prompt)
    return gemini_response

def _set_offer_batch_affinity_by_gemini_response(gemini_response, offers_list):
    """
        Recibe respuesta de gemini con el siguiente formato:
            id-calificacion;di-calificacion...

        Y ajusta la afinidad de cada oferta correspondiente.

    """
    i = 0
    for calification_pairs in gemini_response.split(';'):
        id_, calification = calification_pairs.split('_')
        for o in offers_list:
            if str(o.id) == id_:
                success(f"Afinidad asignada a oferta : {o.id}")
                i +=1
                o.affinity = int(calification)




def offer_list_affinity_handler(offers_list, batch_size=OFFER_BATCH_SIZE):
    """
        Se encarga de tomar toda la lista de ofertas y ajustar su afinidad
        por batches cuyo tamanio esta determinado por OFFER_BATCH_SIZE
    """
    i = 0
    offer_batch = None
    non_set_affinity_offer_list = [o for o in offers_list if not o.affinity]
    if len(non_set_affinity_offer_list) > 0:
        while i != -1:
            if (len(non_set_affinity_offer_list)-i) < batch_size:
                offer_batch = non_set_affinity_offer_list[i:]
                i = -1
            else:
                offer_batch = non_set_affinity_offer_list[i:i+batch_size]
                i+=batch_size
            print(f"Enviando {len(offer_batch)} ofertas a gemini para encontrar su afinidad")
            try:
                gemini_response = _get_offer_batch_affinity(offer_batch)
                print(f"Respuesta de gemini: {gemini_response}")
                _set_offer_batch_affinity_by_gemini_response(gemini_response, offer_batch)
            except Exception as e:
                error("Error en el consumo de gemini, saliendo del bucle")
                error(str(e))
                break
    else:
        print("Todas las ofertas dispuestas cuentan ya con afinidad !")

