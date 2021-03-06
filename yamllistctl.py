#!/usr/bin/env python

import argparse
import logging
import re
import sys
import yaml


log = None


# This helps to improve YAML formatting
class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)


def str_to_bool(value):
    if isinstance(value, bool):
        return value
    elif value.lower() in ['false', '0', 'no', 'n']:
        return False
    elif value.lower() in ['true', '1', 'yes', 'y']:
        return True

    raise ValueError('Value %s is not a valid boolean value' % value)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Search, add or remove host from YAML List inventory "
        "file.")

    parser.add_argument(
        '-f', '--file',
        required=True,
        help="Inventory file.")
    parser.add_argument(
        '-s', '--stdout',
        action='store_true',
        help="Print result to stdout instead of back into the file.")
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help="Show debug messages.")

    subparsers = parser.add_subparsers(help="Actions.")

    parser_search = subparsers.add_parser(
        'search',
        help="Search for host.")
    parser_search.set_defaults(action='search')
    parser_search.add_argument(
        'host',
        help="Name of the host.")

    parser_add = subparsers.add_parser(
        'add',
        help="Add host.")
    parser_add.set_defaults(action='add')
    parser_add.add_argument(
        'host',
        help="Name of the host.")
    parser_add.add_argument(
        'ip',
        nargs='?',
        help="IP of the host.")
    parser_add.add_argument(
        'group',
        nargs='?',
        help="Comma-separated list of groups.")
    parser_add.add_argument(
        '-o', '--override_ungrouped',
        default=True,
        const=True,
        nargs='?',
        metavar='BOOL',
        type=str_to_bool,
        help="Set override_ungrouped (default: true).")

    parser_set = subparsers.add_parser(
        'set',
        help="Set host's property.")
    parser_set.set_defaults(action='set')
    parser_set.add_argument(
        'host',
        help="Name of the host.")
    parser_set.add_argument(
        'path',
        help="Path where to insert the value.")
    parser_set.add_argument(
        'value',
        help=(
            "Value which will be inserted into the path. "
            "Is evaluated as YAML data. "
            "Set value to 'null' to remove the path."))

    parser_remove = subparsers.add_parser(
        'remove',
        help="Remove host.")
    parser_remove.set_defaults(action='remove')
    parser_remove.add_argument(
        'host',
        help="Name of the host to remove.")

    return parser, parser.parse_args()


def read_yaml_file(args):
    log.debug("Reading YAML inventory %s" % args.file)

    data = []

    with open(args.file, 'r') as stream:
        try:
            data = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            log.error("Cannot parse YAML file: %s" % e)
            sys.exit(1)

    if data is None:
        data = []

    return data


def write_yaml_file(data, args):
    if args.stdout:
        log.debug("Printing to STDOUT")

        output = sys.stdout
    else:
        log.debug("Printing back to file")

        try:
            output = open(args.file, 'w')
        except IOError as e:
            log.error("Cannot open file '%s' for write.\n%s" % (args.file, e))

    output.write("---\n\n")
    output.write(yaml.dump(data, Dumper=MyDumper, default_flow_style=False))

    if not args.stdout:
        try:
            output.close()
        except IOError as e:
            log.error("Cannot close file '%s'.\n%s" % (args.file, e))


def search(data, args):
    log.debug("Searching for host: %s" % args.host)

    for i in data:
        if 'name' in i and i['name'] == args.host:
            sys.stdout.write(
                yaml.dump([i], Dumper=MyDumper, default_flow_style=False))

            break


def add(data, args):
    log.debug("Adding host: %s" % args.host)

    found = False

    for i in data:
        if 'name' in i and i['name'] == args.host:
            log.warning("Host already exists.")

            found = True

            if args.ip is not None and args.ip != '':
                if 'ip' not in i:
                    log.info("Had no IP defined")

                    i['ip'] = args.ip
                elif i['ip'] != args.ip:
                    log.info("Had different IP: %s" % i['ip'])

                    i['ip'] = args.ip

            if args.group and args.group != '':
                groups = args.group.split(',')

                if len(groups) == 1:
                    groups = groups[0]

                if (
                        'ansible' in i and
                        'group' in i['ansible'] and
                        i['ansible']['group'] != groups):
                    log.info(
                        "Had different ansible.group: %s" %
                        i['ansible']['group'])

                    i['ansible']['group'] = groups
                elif (
                        'ansible' not in i or
                        'group' not in i['ansible']):
                    log.info("Setting ansible.group")

                    if 'ansible' not in i:
                        i['ansible'] = {}

                    i['ansible']['group'] = groups

            if (
                    (
                        (
                            'ansible' not in i or
                            'override_ungrouped' not in i['ansible']
                        ) and
                        not args.override_ungrouped
                    ) or (
                        'ansible' in i and
                        'override_ungrouped' in i['ansible'] and
                        not args.override_ungrouped and
                        i['ansible']['override_ungrouped'])):
                log.info("Setting ansible.override_ungrouped: false")

                if 'ansible' not in i:
                    i['ansible'] = {}

                i['ansible']['override_ungrouped'] = args.override_ungrouped

            break

    if not found:
        record = {
            'name': args.host,
        }

        if args.ip is not None and args.ip != '':
            record['ip'] = args.ip

        data.append(record)

        if args.group and args.group != '':
            if 'ansible' not in data[-1]:
                data[-1]['ansible'] = {}

            groups = args.group.split(',')

            if len(groups) == 1:
                groups = groups[0]

            data[-1]['ansible']['group'] = groups

        if args.override_ungrouped:
            if 'ansible' not in data[-1]:
                data[-1]['ansible'] = {}

            data[-1]['ansible']['override_ungrouped'] = args.override_ungrouped


def set(data, args):
    log.debug("Setting property: %s" % args.path)

    h_data = None

    for n, i in enumerate(data):
        if 'name' in i and i['name'] == args.host:
            h_data = i

            break

    if h_data is None:
        log.error("No such host was found.")
        sys.exit(127)

    try:
        value = yaml.safe_load(args.value)
    except yaml.YAMLError as e:
        log.error("Cannot parse value as YAML: %s" % e)
        sys.exit(1)

    path = args.path.split('.')
    path_len = len(path)

    for i, elem in enumerate(path):
        if i + 1 == path_len:
            last = True
        else:
            last = False

        el_match = re.match(r'(.*)\[(\d+)\]$', elem)

        if el_match is None:
            key = elem
            index = None
        else:
            key = el_match.group(1)
            index = int(el_match.group(2))

        if key in h_data:
            if index is None:
                if last:
                    if value is None:
                        del h_data[key]
                    else:
                        h_data[key] = value
                else:
                    if (
                            isinstance(h_data[key], list) or
                            isinstance(h_data[key], dict)):
                        h_data = h_data[key]
                    else:
                        log.error(
                            "Key value '%s' is not list or dict." % elem)
                        sys.exit(1)
            else:
                if isinstance(h_data[key], list):
                    if abs(index) < len(h_data[key]):
                        if last:
                            if value is None:
                                del h_data[key][index]
                            else:
                                h_data[key][index] = value
                        else:
                            if (
                                    isinstance(h_data[key][index], list) or
                                    isinstance(h_data[key][index], dict)):
                                h_data = h_data[key][index]
                            else:
                                log.error(
                                    "Indexed value of '%s' is not list or "
                                    "dict." % elem)
                                sys.exit(1)
                    else:
                        log.error("Key index '%s' is out of range." % elem)
                        sys.exit(127)
                else:
                    log.error("Key '%s' is not list." % key)
                    sys.exit(127)
        else:
            if index is None:
                if last:
                    if value is not None:
                        h_data[key] = value
                    else:
                        log.warn("Cannot remove non-existing key '%s'." % key)
                else:
                    h_data[key] = {}
                    h_data = h_data[key]
            else:
                log.error(
                    "Cannot create non-existing indexed value '%s'." % elem)
                sys.exit(127)


def remove(data, args):
    log.debug("Removing host: %s" % args.host)

    for n, i in enumerate(data):
        if 'name' in i and i['name'] == args.host:
            break
    else:
        n = None

    if n is None:
        log.warn("No such host was found.")
    else:
        del data[n]


def main():
    # Read command line arguments
    parser, args = parse_args()

    # Setup logger
    format = "%(levelname)s: %(message)s"
    log_level = logging.ERROR

    if args.debug:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level, format=format)

    global log
    log = logging.getLogger(__name__)

    # Check input parameters
    if 'action' not in args:
        log.error('No action specified!')
        parser.print_help()
        sys.exit(1)

    # Read the YAML file
    data = read_yaml_file(args)

    # Decide what to do
    if args.action == 'search':
        search(data, args)
    elif args.action == 'add':
        add(data, args)
    elif args.action == 'set':
        set(data, args)
    elif args.action == 'remove':
        remove(data, args)

    # Write YAML data back into the file
    if args.action != 'search':
        write_yaml_file(data, args)


if __name__ == '__main__':
    main()
