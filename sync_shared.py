from rich.console import Console
from time import strftime
import socket
import json
import sys

# maximum transition unit (maximum buffer size socket connection)
MTU = 4096
# Fix the header size to 128 bytes
HEADER_SIZE = 128
# This string indicates that a segment has finished sending
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"

# Ansi color codes
C_RESET = '\u001b[0m'
C_WHITE = '\u001b[37m'

console = Console()

# To be set in watcher_server and watcher_client to server and client respectively
user = 'SERVER'


# Logging

def log_time():
    # Make text dim white with C_WHITE
    print(f'{C_WHITE}[{strftime("%X")}]{C_RESET}', end='')

def info(message: str):
    print()
    log_time()
    console.print(f" [bold #000000 on #57c7ff] INFO [/bold #000000 on #57c7ff] [#57c7ff]{message}[/#57c7ff]")
    

def done(message: str):
    print()
    log_time()
    console.print(f" [bold #000000 on #5af78e] DONE [/bold #000000 on #5af78e] [#5af78e]{message}[/#5af78e]")

def warn(message: str):
    print()
    log_time()
    console.print(f" [bold #000000 on #f3f99d] WARN [/bold #000000 on #f3f99d] [#f3f99d]{message}[/#f3f99d]")

def fail(message: str):
    print()
    log_time()
    console.print(f" [bold #000000 on #ff5c57] FAIL [/bold #000000 on #ff5c57] [#ff5c57]{message}[/#ff5c57]")


# Socket stuff

def send(socket: socket.socket, message: str, content_type="message"):
    """send a message from a socket"""
    try:
        # encode message to bytes if not already done
        if type(message) != bytes:
            message = message.encode(FORMAT)

        # Prepare the header
        send_length = len(message)
        headers = {
            "content-type": content_type,
            "content-length": send_length
        }
        header_string = json.dumps(headers).encode(FORMAT)
        header_string += b' ' * (HEADER_SIZE - len(header_string))

        # First send the header then the actual message
        socket.send(header_string)
        socket.send(message)
    except socket.error as msg:
        fail("Could not send message.")
        fail(msg)
        sys.exit(1)


# Testing
if __name__ == "__main__":
    info("info")
    done("success")
    warn("warning!")
    fail("Fatal error occured. Please try again!")
elif __name__ == "sync_shared":
    # Setup code
    info(f"Logging from {user} side")

