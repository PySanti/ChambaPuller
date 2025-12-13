class Offer:
    def __init__(self, link, reception_date) -> None:
        self.link = link
        self.reception_date = reception_date
        self.affinity = None
        self.description = None

    def __str__(self) -> str:
        return f"""
            __________________________________________
            |   Offer Data:
            |---------------
            |   Link : {self.link}
            |   Reception_date: {self.reception_date}
            |   Affinity :  {self.affinity}
            |   Description : {self.description}
            __________________________________________
        """
