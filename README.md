# Sync Files

description...

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
Clone this repository on your machine(s) and go to the cloned folder
```s
git clone https://github.com/Casper64/sync_files.git
cd sync_files
```

## Usage
### Server
For the server use `sync_server.py`.
In this example we bind the server to `localhost:9090` and output the documents to `dist/`.
```sh
python sync_server.py --output dist --port 9090
```

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
  
## License
Distributed under the MIT License. See LICENSE for more information.
