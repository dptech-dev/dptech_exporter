import argparse
import sys
import time
import traceback

import collector
from collector import collector_start
from config import config_init

VERSION = "1.0.0"

from prometheus_client import start_http_server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prometheus exporter for DPtech network devices')
    parser.add_argument('-f', '--file', default='/etc/dptech_exporter.yml', help='configure file, default: /etc/dptech_exporter.yml')
    parser.add_argument('-p', '--port', type=int, default=9091, help='http port, default: 9091')
    parser.add_argument('-d', '--debug', required=False, action='store_true', help='print exception stack')
    parser.add_argument('-v', '--version', dest='print_version', required=False, action='store_true', help='print version')
    args = parser.parse_args()

    if args.print_version:
        print(f"Version {VERSION}")
        sys.exit()

    try:
        collector.debug = args.debug
        config_init(args.file)
        collector_start()
        start_http_server(args.port)

        while True:
            time.sleep(300)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        else:
            print(f'{str(e)}')
