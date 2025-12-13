from utils.MACROS import BASE_PROMPT

def generate_prompt(offers):
    descrptions_section = "\n".join([f"\n\n###OFFER_ID  : {o.id}\n\nDESCRIPTION: {o.description}" for o in offers])
    return BASE_PROMPT+descrptions_section
