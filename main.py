from utils.get_last_offers import get_last_offers

for a in get_last_offers(limit=10):
    print(a['subject'])
    for l in a['links']:
        print(l)
    print("________________")
