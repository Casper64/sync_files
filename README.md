# Sync Files

![python 3.10](https://img.shields.io/badge/Python-3.10-brightgreen?logo=python)
![license](https://img.shields.io/badge/license-MIT-blue)

Synchronize documents from one host to another in real-time.

## About Sync Files

I've created this project during my computer networking class as a tool for myself. I needed to edit files on my raspberry pi without the use of a seperate screen and keyboard. Could I have better worked with a tool like NeoVim in the ssh terminal? Yes, probably. But this was way more fun and on top of that I got to use the theory I had learned and put it to practice. Plus I could use VSCode :+1:.

### Disclaimer:
The socket messages are not encryped. Read the [security](#security) section for more information.

## Getting Started
### Prerequisites

Both the server and client side depend on [rich](https://github.com/Textualize/rich) to enable pretty logs and you can install [rich](https://github.com/Textualize/rich) with `pip` or your favorite PyPI package manager.
```sh
python -m pip install rich
```
Only the client depends on [watchdog](https://github.com/gorakhargosh/watchdog/) to listen to file and folder changes. You can install [watchdog](https://github.com/gorakhargosh/watchdog/) with `pip` or your favorite PyPI package manager.
```sh
python -m pip install watchdog
```

### Installing
Clone this repository on your machine(s) and navigate to the cloned folder.
```sh
git clone https://github.com/Casper64/sync_files.git
cd sync_files
```

### Server
Navigate to the `server` folder on your server side and start listening for a connection by executing `sync_server.py`.
```sh
cd server
python ../sync_server.py
```
### Client
Navigate to the `client` folder on your client side and execute `sync_client.py` to connect to the server.
```sh
cd client
python ../sync_client.py
```

## Usage
### Server
For the server use `sync_server.py`.
In this example we bind the server to `localhost:9090` and output the documents to `dist/`.
```sh
python sync_server.py --output dist --port 9090
```

You can use `--host 0.0.0.0` if you want to transmit files that are on another machine. The host `0.0.0.0` basically means to listen to connections from every ip-addres instead of only connection from the machine itself, the localhost.

### Client
For the client use `sync_client.py`.
If we want to watch the `src/` directory on the client we only need to specify the port since the servers default value is `localhost`.
```sh
python sync_server.py --input src --port 9090
```

## Configuration
All configuration can be placed in a dedicated `sync.conf` file.

`server/sync.conf`
```
host=localhost
port=9090
output=output
```

### Server
```sh
> python sync_server.py -h
usage: sync_server.py [-h] [-o OUTPUT] [--host HOST] -p PORT

Receive incoming files and output them in the right place. If no options are specified
the sync.conf file will be used in the current directory

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        the directory to output to. Defaults to the current directory
  --host HOST           the host to bind the socket to. Defaults to localhost
  -p PORT, --port PORT  the port to bind the server to
```
### Client
```sh
> python sync_client.py -h
usage: sync_client.py [-h] [-i INPUT] [-s SERVER] -p PORT

Watch files and upload to a server. If no options are specified the sync.conf file will
be used in the current directory

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        the directory to watch. Defaults to the current directory
  -s SERVER, --server SERVER
                        the servers ip address
  -p PORT, --port PORT  the port on the server
  ```  

## Security
This project doesn't utilize TLS and messages are not encrypted! This project was meant to transfer my files locally via a direct ethernet link and isn't meant to sent traffic over the internet.

Don't expect this project to transmit large files (100MB+). The reason why is explained in `sync_client.py` in the `on_modified` and `send_file` methods. It's possible to fix this bug, but is out of the scope of this project.
  
## License
Distributed under the MIT License. See LICENSE for more information.
