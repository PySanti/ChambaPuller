def remove_duplicated_offers(offer_list):
    cleaned_total_offers = []
    for offer in offer_list:
        if offer.id not in [o.id for o in cleaned_total_offers]:
            cleaned_total_offers.append(offer)
    return cleaned_total_offers


