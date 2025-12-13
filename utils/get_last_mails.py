import os
import imaplib
import email
from dotenv import load_dotenv

def get_last_mails(n_correos=10):
    """
    Se conecta a Gmail usando IMAP y una Contraseña de Aplicación.
    Retorna el asunto y remitente de los N correos más recientes.
    """
    load_dotenv()
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    IMAP_SERVER = os.getenv("IMAP_SERVER")

    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Error: Asegúrate de definir GMAIL_USER y GMAIL_APP_PASSWORD en tu .env")
        return []

    # 2. Conexión y Login
    print(f"Intentando conectar a {IMAP_SERVER}...")
    try:
        # Conexión segura (SSL) al servidor IMAP de Gmail
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    except imaplib.IMAP4.error as e:
        print(f"Error de conexión o login IMAP: {e}")
        print("Asegúrate de haber habilitado la Contraseña de Aplicación en tu cuenta de Google.")
        return []

    # 3. Seleccionar la bandeja de entrada
    # 'readonly=True' evita que el script pueda modificar, mover o borrar correos.
    mail.select('inbox', readonly=True)

    # 4. Buscar IDs de todos los correos
    # El comando 'ALL' retorna los IDs de todos los mensajes
    status, email_ids_data = mail.search(None, 'ALL')
    
    # Decodificar y convertir los IDs a una lista de números
    email_ids = email_ids_data[0].split()
    
    if not email_ids:
        print("No se encontraron correos en la bandeja de entrada.")
        mail.logout()
        return []

    # 5. Seleccionar los IDs de los N correos más recientes
    # Los IDs están en orden ascendente (más antiguo a más nuevo), así que tomamos el final
    recent_email_ids = email_ids[-n_correos:]
    
    lista_correos = []
    print(f"Obteniendo detalles de los últimos {len(recent_email_ids)} correos...")

    # 6. Iterar sobre los IDs y obtener el contenido
    for email_id in reversed(recent_email_ids): # Los procesamos del más nuevo al más antiguo
        # Comando 'FETCH' para obtener la cabecera completa (RFC822) del correo
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        # El contenido del mensaje viene como bytes, lo parseamos con la biblioteca 'email'
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        # Extraer información clave
        subject = msg.get('subject', 'Sin Asunto')
        sender = msg.get('from', 'Desconocido')
        
        # NOTA: La decodificación del cuerpo del mensaje (plaintext o HTML) es compleja
        # debido a la estructura MIME anidada. Aquí nos limitaremos a cabeceras.
        
        # Decodificar el Asunto si es necesario
        try:
            # decode_header maneja asuntos con codificación como =?utf-8?B?XXX?=
            decoded_subject = email.header.decode_header(subject)[0][0]
            if isinstance(decoded_subject, bytes):
                # Si el resultado es bytes, intentamos decodificar a utf-8
                subject = decoded_subject.decode('utf-8', errors='ignore')
            else:
                subject = decoded_subject
        except:
            # En caso de error de decodificación, usamos el original
            pass

        correo_info = {
            'asunto': subject,
            'remitente': sender
        }
        lista_correos.append(correo_info)

    # 7. Cerrar la conexión
    mail.logout()
    print("Conexión IMAP cerrada.")
    
    return lista_correos

