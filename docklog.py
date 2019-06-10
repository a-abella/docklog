#!/usr/bin/env python3

import argparse
import docker
import errno
import os
import random
import re
import sys
import time
from colorama import init, deinit, Back, Style
from multiprocessing import Process
from signal import signal, SIGPIPE, SIG_DFL
# Handle SIGPIPE from kb interrupts while grepping, etc.
signal(SIGPIPE,SIG_DFL) 

# Limit maximum container log streams to 8
# TODO: tune this, measure impact on docker daemon
def maximum_length(nmax):
    class MaximumLength(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if not len(values) <= nmax:
                msg="too many {} arguments: {}. Max 8".format(self.dest,len(values))
                raise argparse.ArgumentTypeError(msg)
            setattr(args, self.dest, values)
    return MaximumLength

# Print a docker log stream
def stream_log(container, color):
    # Retrieve log lines live as a byte stream
    # Decode, prepend formatting, and print
    try:
        for line in container.logs(stream=True, timestamps=args.timestamps, tail=args.tail):
            print(color + container.name + Style.RESET_ALL + "\t\t|  " + line.decode().strip(), flush=True)
    except KeyboardInterrupt:
        return 1

# Parse arguments and options
# Print error if too many containers
parser = argparse.ArgumentParser(description="Simultaneously stream the logs of up to eight Docker containers")
parser.add_argument("container", metavar="CONTAINER", help="Container names or IDs", type=str, nargs="+", action=maximum_length(8))
parser.add_argument("-t", "--timestamps", "--time", help="Prepend timestamps to log lines", action="store_true")
parser.add_argument("-n", "--tail", help="Number of lines to show from end of the logs (default 10)", type=int, default=10)
try:
    args = parser.parse_args()
except argparse.ArgumentTypeError as err:
    parser.print_usage()
    print(os.path.basename(sys.argv[0]) + ": " + "error: " + str(err))
    sys.exit(1)

# Hold used colors and init ANSI sequences in win32
usedcolors = []
init(strip=False)

# Hold our multiple clients
clients = []

# Hold our log stream child processes
streams = []

# Create a log stream for each container
for container in args.container:
    # Always get a new color for container names
    while True:
        if len(usedcolors) >= 5:
            colorcode = random.randrange(91,96)
        else:
            colorcode = random.randrange(31,36)

        if not colorcode in usedcolors:
            usedcolors.append(colorcode)
            break
    color = Style.BRIGHT + "\033[" + str(colorcode) + "m"

    # Connect to docker using DOCKER_HOST env var
    client = docker.from_env(version='auto', assert_hostname=False)
    clients.append(client)
    
    # Get container by name or ID from supplied command-line arguments
    try:
        container = client.containers.get(container)
    # Handle failed container lookups
    except:
        print("\n" + Style.BRIGHT + "\033[31mError" + Style.RESET_ALL + ": Could not find container '" + container + "'")
        for stream in streams:
            stream.terminate()
        for client in clients:
            client.close()
        deinit()
        print()
        sys.exit(1)

    # Spawn a child processes for each container log stream
    # Do not block or buffer
    p = Process(target=stream_log, args=(container, color))
    streams.append(p)
    p.start()

# Keep main thread alive while streaming
try:
    while True:
        time.sleep(1)
# Clean up child processes and close docker client connections
except:
    for stream in streams:
        stream.terminate()
    for client in clients:
        client.close()
# De-colorize and exit
finally:
    deinit()
    print()
    sys.exit()