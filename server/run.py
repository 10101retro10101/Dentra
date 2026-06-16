import os
import threading
from django.core.management import execute_from_command_line
import webview
import time
from server.WebTable.WebTable import decrementSessions
import ujson as json
import signal
import sys
import atexit

def run_django_server():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")
    execute_from_command_line(["manage.py", "runserver", "--noreload"])

def create_app():
    webview.create_window(
        "Dentra",
        "http://127.0.0.1:8000/",
        width=1350,  # Ширина окна
        height=800,  # Высота окна
    )
    webview.start()

def exitProgram() -> None:
    with open("./server/WebTable/table_state.json", "r") as file:
        user_key = json.loads(file.read()).get("cur_user_key", "")
    if user_key:
        decrementSessions(user_key=user_key)
    print("User session is closed")
    return

def _signal_handler(sig, frame):
    exitProgram()
    sys.exit(0)

def main() -> None:
    django_thread = threading.Thread(target=run_django_server)
    django_thread.daemon = True
    django_thread.start()
    time.sleep(3)
    create_app()


if __name__ == "__main__":
    atexit.register(exitProgram)
    # signal.signal(signal.SIGINT, _signal_handler)
    # signal.signal(signal.SIGTERM, _signal_handler)  # systemd, docker stop, kill
    # if hasattr(signal, 'SIGHUP'):
    #     signal.signal(signal.SIGHUP, _signal_handler)

    main()