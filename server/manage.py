#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
# import atexit
from server.WebTable.WebTable import decrementSessions
import ujson as json
import signal

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

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

if __name__ == '__main__':
    # atexit.register(exitProgram)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)  # systemd, docker stop, kill
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _signal_handler)

    main()
