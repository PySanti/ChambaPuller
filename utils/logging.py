from colorama import Fore
def success(msg):
    print(Fore.GREEN + msg + Fore.RESET)

def error(msg):
    print(Fore.RED + msg + Fore.RESET)