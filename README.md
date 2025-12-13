# ChambaPuller

Este proyecto tiene como objetivo crear un bot para la automatización de filtrado de ofertas de trabajo.

Llevo varios meses buscando trabajo como ingeniero junior en machine learning y tengo la problemática de no poder encontrar muchas ofertas que se ajusten realmente a mi perfil e intereses.

Este proyecto implementará un pipeline para:

Procesar alertas de empleo que lleguen a mi email.
Para todas las ofertas de empleo crear objetos Offer, los cuales contendrán : link, description, affinity, reception_date.
Luego de cargar las ofertas a través del email, se realizará una consulta HTTP para obtener la descripción del puesto, dicha descripción será agregada al atributo description.
Luego para cada oferta, se le enviará su descripción a gemini, ademas, se enviara el cv y un prompt que contenga mis intereses en el puesto que busco.
Gemini responderá a la consulta con un valor en un rango del 1 al 10, que representa la afinidad de mi perfil con el puesto.
Luego, todas las ofertas serán agregadas a un google sheets, volcando todos los campos de la oferta sobre el sheets.
Además, se contará con un sheets que contendrá todas las ofertas filtradas.
Se cargarán las ofertas contenidas en ese sheets, se eliminaran las que estén duplicadas, y luego se volcara todo sobre el sheets.

Nota: para cargar los correos se tomará un argumento desde el CLI que represente la cantidad de días desde los cuales se quieran traer las ofertas (ej. 100  para traer todas las ofertas en los últimos 100 días).

Nota: se agregara una lógica para evitar cargar ofertas que ya hayan sido procesadas.

# Dificultades/Limitaciones

A continuación se listan los obstáculos con los que me podré enfrentar

La cantidad de correos a traer desde gmail
La cantidad de peticiones por minuto que se le pueden hacer a linkedin.
La cantidad de solicitudes por minuto que se le pueden hacer a gemini
La posibilidad de subir un archivo a gemini (el CV)
