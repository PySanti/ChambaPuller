from __future__ import annotations

from utils.get_offer_description import get_offer_description
import uuid

class Offer:
    def __init__(self, link, reception_date, father_mail_subject) -> None:
        self.id = uuid.uuid4()
        self.link = link
        self.reception_date = reception_date
        self.father_mail_subject = father_mail_subject
        self.affinity = None
        self.description = None

    def __str__(self) -> str:
        return f"""
            __________________________________________
            |   Offer Data:
            |---------------
            |   Offer id        : {self.id}
            |   Link            : {self.link}
            |   Mail Subject    : {self.father_mail_subject}
            |   Reception_date  : {self.reception_date}
            |   Affinity        : {self.affinity}
            |   Description     : {self.description[:5]+'...' if self.description else self.description}
            __________________________________________
        """
    def set_description(self):
        self.description = get_offer_description(self.link)



