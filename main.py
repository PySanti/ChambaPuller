from utils.get_last_offers import get_last_offers
from utils.get_offer_description import get_offer_description
from time import sleep

for a in get_last_offers(limit=10):
    print(f"Recibido en : {a.reception_date}")
    print(get_offer_description(a.link))
    sleep(5)
    

