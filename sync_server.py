#!/usr/bin/python3

import json
import os
import socket
import sys
from argparse import ArgumentParser
from genericpath import isfile
from shutil import rmtree
import rich.progress
import traceback

import sync_shared

class ServerSocketHandler:
    _socket: socket.socket
    host: str
    port: int
    output_path: str
    message_headers = {}

    def __init__(self):
        self._parse_args()
        sync_shared.info("Logging from SERVER side")

    def _parse_args(self):
        """parse cli arguments/config file"""
        # Parse arguments from the cli
        parser = ArgumentParser(description="Receive incoming files and output them in the right place. If no options are specified the sync.conf file will be used in the current directory")
        parser.add_argument('-o', '--output', help="the directory to output to. Defaults to the current directory")
        parser.add_argument('--host', default="localhost", help="the host to bind the socket to. Defaults to localhost")
        parser.add_argument('-p', '--port', required=True, type=int, help="the port to bind the server to")

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

        args = parser.parse_args(arguments)
        self.host = args.host
        self.port = args.port
        # Convert the given path argument to an absolute path
        self.output_path = os.path.abspath(args.output) if args.output is not None else os.getcwd()

        # Don't remove entire filesystem safeguard lol
        if self.output_path.count('/') == 1 or self.output_path.count('\\') == 1:
            sync_shared.fail("Can't choose this directory! Be careful this would destroy your file system")
            sys.exit(1)

    def start(self):
        """listen to an incoming connection and end program when the connection is closed"""
        try:
            (connection, adress) = self._socket.accept()

            sync_shared.done(f"Connection accepted from {adress[0]}:{adress[1]}")
            connected = True
            while connected:
                message_headers = connection.recv(sync_shared.HEADER_SIZE).decode(sync_shared.FORMAT)
                if message_headers:
                    self.message_headers = json.loads(message_headers)

                    # Handle content types that aren't messages
                    if self.message_headers["content-type"] == "file":
                        self._handle_file(connection)
                        continue
                    elif self.message_headers["content-type"] == "event":
                        self._handle_event(connection)
                        continue

                    # Handle messages
                    msg_length = self.message_headers["content-length"]
                    msg = connection.recv(msg_length).decode(sync_shared.FORMAT)

                    # Stop the loop if the DISCONNECT_MESSAGE is sent.
                    if msg == sync_shared.DISCONNECT_MESSAGE:
                        connected = False
                        sync_shared.warn(f"[{adress[0]}:{adress[1]}]: wants to close the connection!")
                    else:
                        sync_shared.info(f"[{adress[0]}:{adress[1]}]: {msg}")

        # Send a disconnect message to the client when an error occurs
        except socket.error as err:
            sync_shared.fail("A socket error occured:")
            sync_shared.fail(str(err))
            sync_shared.warn("Closing connection")
            sync_shared.send(connection, sync_shared.DISCONNECT_MESSAGE)
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except Exception as e:
            sync_shared.fail("An error has occured:")
            traceback.print_exception(e)
            sync_shared.warn("Closing connection")
            sync_shared.send(connection, sync_shared.DISCONNECT_MESSAGE)
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        finally:
            connection.close()

        # The connection was closed by the user or an error occurred so the socket can be closed on the server side
        sync_shared.done("Connection closed")

    def _handle_file(self, conn: socket.socket):
        # get the file header length
        file_header_length = self.message_headers["content-length"]
        # wait for the file headers
        file_headers = conn.recv(file_header_length).decode(sync_shared.FORMAT)
        file_headers = json.loads(file_headers)

        # total length of the file that will be sent
        total_length = int(file_headers["file-length"])

        # Show progress bar
        
        path = os.path.join(self.output_path, file_headers["path"])

        with rich.progress.Progress(
            rich.progress.TextColumn("{task.description}"),
            rich.progress.BarColumn(),
            rich.progress.FileSizeColumn(),
            rich.progress.TotalFileSizeColumn(),
            rich.progress.TimeRemainingColumn()
        ) as progress:
            write_task = progress.add_task(f"Writing {file_headers['path']}...", total=total_length)
            with open(path, 'wb') as f:
                should_end = False
                while should_end == False and total_length > 0:
                    # The next buffer size will always be the constant MTU, except if the remaining file length is smaller than the MTU.
                    if total_length < sync_shared.MTU:
                        next_buffer_size = total_length
                    else:
                        next_buffer_size = sync_shared.MTU
                    # Decrease the total length of the remaining bytes sent
                    total_length -= next_buffer_size

                    # Wait for the data from the client and append it to the file
                    data = conn.recv(next_buffer_size)

                    if not data and total_length == 0:
                        should_end = True
                    # Something went wrong with sending the data
                    elif not data:
                        total_length += next_buffer_size
                        continue

                    f.write(data)

                    progress.update(write_task, advance=next_buffer_size)

        # TODO?: send a receipt back

    def _handle_event(self, conn: socket.socket):
        """handle all content-type: 'event' messages from the client"""
        # get the file header length
        event_header_length = int(self.message_headers["content-length"])
        # wait for the event headers
        event_headers = conn.recv(event_header_length).decode(sync_shared.FORMAT)
        event_headers = json.loads(event_headers) 

        if "source-path" in event_headers:
            relative_source = event_headers["source-path"]
            event_headers["source-path"] = os.path.join(self.output_path, event_headers["source-path"])

        try:
            if event_headers["event-type"] == "created":
                if event_headers["directory"]:
                    os.mkdir(event_headers["source-path"])
                else:
                    f = open(event_headers["source-path"], 'wb')
                    f.close()
                
                sync_shared.done(f"Created { 'directory' if event_headers['directory'] else 'file' } '{relative_source}'")
            elif event_headers["event-type"] == "clear":
                f = open(event_headers["source-path"], 'wb')
                f.close()

                sync_shared.done(f"Cleared file '{relative_source}'")
            elif event_headers["event-type"] == "deleted":
                # Try to delete path as a file, if that errors it must be a directory.
                # This workaround is needed, because watchdog can't determine wether a deleted path was a directory or not
                try:
                    os.remove(event_headers["source-path"])
                except:
                    rmtree(event_headers["source-path"], True)

                sync_shared.done(f"Deleted '{relative_source}'")
            elif event_headers["event-type"] == "sync":
                # Remove old tree and make new directory.
                sync_shared.info("Syncing file tree...")

                rmtree(self.output_path, True)
                os.mkdir(self.output_path)
                
        except Exception as e:
            # Ignore errors for now
            sync_shared.fail(f"Failed to process '{event_headers['event-type']}' event with error:")
            sync_shared.fail(str(e))
            pass


def main():
    socket_handler = ServerSocketHandler()

    try:
        # Create the actual socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((socket_handler.host, socket_handler.port))
        server.listen()

        sync_shared.info(f"Outputting to directory {socket_handler.output_path}")
        sync_shared.info(f"Listening on {socket_handler.host}:{socket_handler.port}")
    except server.error as msg:
        sync_shared.fail("Couldn not open socket.")
        sync_shared.fail(msg)
        sys.exit(1)

    socket_handler._socket = server
    with server:
        # start listening to the socket
        socket_handler.start()
        pass
    
if __name__ == "__main__":
    main()

