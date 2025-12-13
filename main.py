from utils.get_last_mails import get_last_mails

if __name__ == '__main__':
    ultimos_correos = get_last_mails(n_correos=500)
    
    print("\n--- Últimos Correos Obtenidos (IMAP) ---")
    if ultimos_correos:
        for i, correo in enumerate(ultimos_correos):
            print(f"{i+1}. Asunto: {correo['asunto']}")
            print(f"   De: {correo['remitente']}")
            print("-" * 20)
    else:
        print("No se pudo obtener la lista de correos.")
