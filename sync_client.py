import json
from threading import Thread
import time
import os
import socket
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from argparse import ArgumentParser
from genericpath import isfile
import rich.progress

import sync_shared

# Fix VSCode duplciate modified event messages (for small sized files < 50kb or around 800 lines of code)
DUPLICATE_DELAY = 0.5

socket_handler: 'ClientSocket' = None

def create_event_headers(event_type: str, directory:bool=None, source_path:str=None) -> str:
    event_headers = {
        "event-type": event_type
    }
    if directory is not None:
        event_headers["directory"] = directory
    if source_path is not None:
        event_headers["source-path"] = socket_handler.get_relative_path(source_path)
    return json.dumps(event_headers)

class MyHandler(FileSystemEventHandler):
    # Store the previous modified event
    prev_path = {
        "path": '',
        "time": 0
    }

    def on_modified(self,  event):
        """on path modified"""
        # NOTE:
        # VSCode (and maybe other editors) send two file modified events, because they save them twice or write in buffers? idk
        # So the file will be sent twice. It is possible to counter this but not worth enough to code a system that is responsive with the file size
        # e.g. if a text file is over 40mb or so the VSCode will trigger a modified event 3 times so the 40mb file will be sent 3 times
        # This loss could add up to huge delays but that is out of the scope of this project.


        # Don't send modified events when a directory changes or the previous modifed event of the same file was fires less than DUPLICATE_DELAY seconds ago
        if (time.time() - self.prev_path["time"] < DUPLICATE_DELAY and self.prev_path["path"] == event.src_path) or event.is_directory == True:
            return
        
        socket_handler.send_file(event.src_path)
        self.prev_path["time"] = time.time()
        self.prev_path["path"] = event.src_path
        
    def on_created(self,  event):
        """on path created"""
        relative_path = socket_handler.get_relative_path(event.src_path)
        sync_shared.info(f"Created { 'directory' if event.is_directory else 'file' } '{relative_path}'")

        socket_handler.send(create_event_headers(event.event_type, event.is_directory, event.src_path), "event")

    def on_deleted(self,  event):
        """on path deleted"""
        relative_path = socket_handler.get_relative_path(event.src_path)
        sync_shared.info(f"Deleted '{relative_path}'")

        socket_handler.send(create_event_headers(event.event_type, event.is_directory, event.src_path), "event")

# TODO: write class strings and file docstring
class ClientSocket:
    connected = False

    def __init__(self):
        self._parse_args()
        sync_shared.info("Logging from CLIENT side")
        self._connect()

    def send(self, message: str, content_type="message"):
        sync_shared.send(self._socket, message, content_type)

    def send_file(self, path: str):
        """send a file to the server"""

        relative_path = self.get_relative_path(path)

        # give the filesystem some time to reload
        time.sleep(0.2)
        size = os.path.getsize(path)
        count = 0
        # make sure over 50KB files are always checked twice for size.
        prev_size = size if size < 50000 else 0
        while count < 5 and size != prev_size:
            # Vscode fires 2 modified events and is sometimes a little slow, because of that size will be 0
            # So this code cheks up to five times if os.path.getsize yields the same result when run twice
            time.sleep(0.2)
            prev_size = size
            size = os.path.getsize(path)
            count += 1
        # Send a 'clear' event when the file size is 0
        if size == 0:
            self.send(create_event_headers("clear", path), "event")
            return
        if count == 5 or size != prev_size:
            sync_shared.fail(f"Could not send {relative_path}. File is too large!")
            return

        # Show progress bar
        try:
            # Send header
            # The end string length is added to the size
            file_header = {
                "file-length": size,
                "path": relative_path
            }
            file_header = json.dumps(file_header)
            self.send(file_header, "file")
            
            # Pretty progress bar :)
            with rich.progress.Progress(
                rich.progress.TextColumn("{task.description}"),
                rich.progress.BarColumn(),
                rich.progress.FileSizeColumn(),
                rich.progress.TotalFileSizeColumn(),
                rich.progress.TimeRemainingColumn()
            ) as progress:
                read_task = progress.add_task(f"Reading {relative_path}...", total=size)
                with open(path, 'rb') as f:
                    while True:
                        # read the file and send it in segments of the MTU
                        bytes_read = f.read(sync_shared.MTU)
                        if not bytes_read:
                            break
                        # Send the bytes and update the progress bar
                        progress.update(read_task, advance=len(bytes_read))
                        self._socket.sendall(bytes_read)
                
        except socket.error as msg:
            sync_shared.fail(f"Could not send file {path}")
            sync_shared.fail(msg)
            sys.exit(1)

    def get_relative_path(self, path: str):
        """get the relative path from the input directory"""
        relative_path = path.replace(self.input_directory, '').replace('\\', '/')
        if relative_path[0] == '/':
            relative_path = relative_path[1:]
        return relative_path

    def sync(self):
        """Sync the current filetree with the server"""
        self.syncing = True
        socket_handler.send(create_event_headers("sync"), "event")

        # Walk over all files and directories and recreate the filetree at server side
        for root, dirs, files in os.walk(self.input_directory):
            for name in dirs:
                path = os.path.join(root, name)

                socket_handler.send(create_event_headers("create", directory=True, source_path=path), "event")
            for name in files:
                path = os.path.join(root, name)

                socket_handler.send(create_event_headers("create", directory=False, source_path=path), "event")
                socket_handler.send_file(path)

        sync_shared.done("Syncing is done")
        self.syncing = False

    def _parse_args(self):
        """parse cli arguments/config file"""
        # Parse arguments from the cli
        parser = ArgumentParser(description="Watch files and upload to a server. If no options are specified the sync.conf file will be used in the current directory")
        parser.add_argument('-i', '--input', help="the directory to watch. Defaults to the current directory")
        parser.add_argument('-s', '--server', default='localhost', help="the servers ip address")
        parser.add_argument('-p', '--port', required=True, type=int, help="the port on the server")

        arguments = []
        if len(sys.argv) > 1:
            arguments = sys.argv[1:]
        # else get the options from the config file
        else:
            if isfile('sync.conf') == False:
                sync_shared.warn("No sync.conf file found")
                parser.print_help()
                sys.exit(1)
            with open('sync.conf', 'r') as f:
                while line := f.readline():
                    # Append each line as an argument value pair
                    [arg, val] = line.strip().split('=')
                    arguments.append(f"--{arg}")
                    arguments.append(val)

        # parse arguments
        args = parser.parse_args(arguments)
        self.server_ip = args.server
        self.port = args.port
        self.input_directory = os.path.abspath(args.input) if args.input else os.getcwd()
    
        # Don't remove entire filesystem safeguard lol
        if self.input_directory.count('/') == 1 or self.input_directory.count('\\') == 1:
            sync_shared.fail("Can't choose this directory! Be careful this would destroy your file system")
            sys.exit(1)

    def _connect(self):
        """connect socket to the server"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.server_ip, self.port))
            sync_shared.done(f"Connected to {self.server_ip}:{self.port}")

            self.connected = True

            # Make a new thread for incoming messages, because `socket.recv` is a blocking method
            self.incoming_thread = Thread(target=self._handle_messages)
            self.incoming_thread.start()
        except socket.error as msg:
            sync_shared.fail("Could not connect to server.")
            sync_shared.fail(msg)
            sys.exit(1)

    def _handle_messages(self):
        while self.connected:
            message_headers = self._socket.recv(sync_shared.HEADER_SIZE).decode(sync_shared.FORMAT)
            if message_headers:
                message_headers = json.loads(message_headers)
            # If an empty message is sent the conncetion was probably closed by the client. The loop continues and self.connected is checked again
            else:
                continue

             # Handle messages
            msg_length = message_headers["content-length"]
            msg = self._socket.recv(msg_length).decode(sync_shared.FORMAT)

            # Stop the loop if the DISCONNECT_MESSAGE is sent.
            if msg == sync_shared.DISCONNECT_MESSAGE:
                self.connected = False
                sync_shared.warn(f"[SERVER]: wants to close the connection!")
            else:
                sync_shared.info(f"[SERVER]: {msg}")


# TODO?: Wrap socket creation in with statement and put it outside of the class
def main():
    global socket_handler

    socket_handler = ClientSocket()
    socket_handler.sync()

    # Init watchdog file observers
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler,  path=socket_handler.input_directory,  recursive=True)

    sync_shared.info(f"Watching directory {socket_handler.input_directory}")
    observer.start()

    # Keep looping until the user stops the program (ctrl+c), is checked every second
    try:
        while socket_handler.connected:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

        # Properly close the connection
        sync_shared.warn("Disconnecting from the server...")
        socket_handler.connected = False
        socket_handler.send(sync_shared.DISCONNECT_MESSAGE)
    except:
        # Properly close the connection
        sync_shared.warn("Disconnecting from the server...")
        socket_handler.connected = False
        socket_handler.send(sync_shared.DISCONNECT_MESSAGE)

    # The connection is closed at thist moment
    sync_shared.done("Disconnected from the server")


if __name__ == "__main__":
    main()

