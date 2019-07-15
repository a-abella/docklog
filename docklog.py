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
                msg='too many {} arguments: {}. Max 8'.format(self.dest,len(values))
                raise argparse.ArgumentTypeError(msg)
            setattr(args, self.dest, values)
    return MaximumLength

# Print a docker log stream
def stream_log(container, color):
    # Retrieve log lines live as stream
    # Decode (if needed), prepend formatting, and print

    # Some containers return strings and some return byte streams; apparently
    # this has to do with container TTY allocation (docker-py issue 1729). We'll
    # attempt to decode, and if output is char strings then stitch the lines
    # back together.
    if args.timestamps:
        try:
            tabwidth = (bignamewidth - len(container.name)) + 8
            strline = ''
            for line in container.logs(stream=True, timestamps=True, tail=args.tail):
                try:
                    line = line.decode().strip()
                    time = line.split()[0][:22] + 'Z'
                    logline = ' '.join(line.split()[1:])
                    print(color + container.name + Style.RESET_ALL + ' ' * tabwidth + time + '  |  ' + logline, flush=True)
                except AttributeError:
                    if not '\n' in line and not '\r' in line:
                        strline += line
                    if '\n' in line:
                        time = strline.strip().split()[0][:22] + 'Z'
                        logline = ' '.join(strline.strip().split()[1:])
                        strline = ''
                        print(color + container.name + Style.RESET_ALL + ' ' * tabwidth + time + '  |  ' + logline, flush=True)
        except KeyboardInterrupt:
            return 1
    else:
        try:
            tabwidth = (bignamewidth - len(container.name)) + 14
            strline = ''
            for line in container.logs(stream=True, timestamps=False, tail=args.tail):
                try:
                    logline = line.decode().strip()
                    print(color + container.name + Style.RESET_ALL + ' ' * tabwidth  + '|  ' + logline, flush=True)
                except AttributeError:
                    if not '\n' in line and not '\r' in line:
                        strline += line
                    if '\n' in line:
                        logline = strline.strip()
                        strline = ''
                        print(color + container.name + Style.RESET_ALL + ' ' * tabwidth  + '|  ' + logline, flush=True)
        except KeyboardInterrupt:
            return 1

# Print without streaming
def print_log(container, color):
    # Retrieve last N log lines and exit
    # Decode, prepend formatting, and print
    thislog = []
    if args.timestamps:
        try:
            tabwidth = (bignamewidth - len(container.name)) + 8
            for line in container.logs(stream=False, timestamps=True, tail=args.tail).decode().split('\n')[:-1]:
                logline = line.strip()
                time = logline.split()[0][:24] + 'Z'
                logline = ' '.join(logline.split()[1:])
                thislog.append(color + container.name + Style.RESET_ALL + ' ' * tabwidth  + time + '  |  ' + logline)
            return thislog
        except KeyboardInterrupt:
            return 1
    else:
        try:
            tabwidth = (bignamewidth - len(container.name)) + 14
            for line in container.logs(stream=False, timestamps=False, tail=args.tail).decode().split('\n')[:-1]:
                thislog.append(color + container.name + Style.RESET_ALL + ' ' * tabwidth  + '|  ' + line.strip())
            return thislog
        except KeyboardInterrupt:
            return 1

# Parse arguments and options
# Print error if too many containers
parser = argparse.ArgumentParser(description='Simultaneously stream the logs of up to eight Docker containers')
parser.add_argument('container', metavar='CONTAINER', help='Container names or IDs', type=str, nargs='+', action=maximum_length(8))
parser.add_argument('-t', '--timestamps', '--time', help='Prepend timestamps to log lines', action='store_true')
parser.add_argument('-n', '--tail', help='Number of lines to show from end (default 10)', type=int, default=10)
parser.add_argument('-s', '--static', help='Do not follow; print tail lines and exit', action='store_true')
try:
    args = parser.parse_args()
except argparse.ArgumentTypeError as err:
    parser.print_usage()
    print(os.path.basename(parser.prog) + ': ' + 'error: ' + str(err))
    sys.exit(1)

# Hold used colors and init ANSI sequences in win32
usedcolors = []
init(strip=False)

# Hold the largest container name char count
bignamewidth = 0

# Hold our multiple clients
clients = []

# Hold our log stream child processes
streams = []

# Hold static log lines for later sorting
all_lines = []

# Test client connection, get names, find longest
for container in args.container:
    try:
        client = docker.from_env(version='auto', assert_hostname=False)
    except:
        print('\n' + Style.BRIGHT + '\033[31mError' + Style.RESET_ALL + ': Could not connect to docker daemon')
        deinit()
        sys.exit(1)
    try:
        thiscontainer = client.containers.get(container)
    except:
        print('\n' + Style.BRIGHT + '\033[31mError' + Style.RESET_ALL + ': Could not find container '' + container + ''')
        client.close()
        deinit()
        sys.exit(1)
    
    thislength = len(thiscontainer.name)
    bignamewidth = thislength if thislength > bignamewidth else bignamewidth
    client.close()


# Get logs for each container
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
    color = Style.BRIGHT + '\033[' + str(colorcode) + 'm'

    # Connect to docker using DOCKER_HOST env var
    client = docker.from_env(version='auto', assert_hostname=False)
    clients.append(client)
    
    # Get container by name or ID from supplied command-line arguments
    resolved_container = client.containers.get(container)

    # Get logs and hold for sorting if not streaming
    if args.static:
        all_lines.extend(print_log(resolved_container, color))
    # Spawn child processes if streaming
    # Do not block or buffer
    else:
        p = Process(target=stream_log, args=(resolved_container, color))
        streams.append(p)
        p.start()

# Print, clean up, and exit if not streaming
if args.static:
    if args.timestamps:
        for line in sorted(all_lines, key=lambda line: line.split()[1]):
            print(line)
    else:
        for line in all_lines:
            print(line)
    client.close()
    deinit()
    print()
    sys.exit()
# Keep main thread alive while streaming, catch ctrl-c
else:
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
