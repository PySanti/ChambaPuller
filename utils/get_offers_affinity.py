from utils.gemini_query import gemini_query
from utils.generate_prompt import generate_prompt


def get_offers_affinity(offers):
    """
        Hara la consulta a gemini enviando batches de ofertas para aprovechar mejor
        los limites impuestos por gemini

        Gemini respondera con el siguiente formato :
            uuid-calificacion;uudi-calificacion...
    """
    prompt = generate_prompt(offers)
    gemini_response = gemini_query(prompt)
    i = 0
    for calification_pairs in gemini_response.split(';'):
        uuid, calification = calification_pairs.split('_')
        calification = int(calification)
        for o in offers:
            if str(o.id) == uuid:
                print(f"Asignando afinidad de oferta : {o.id}")
                i +=1
                o.affinity = calification
