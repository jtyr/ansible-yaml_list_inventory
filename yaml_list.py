from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = '''
    inventory: yaml_list
    short_description: Uses a specific YAML file as an inventory source.
    description:
      - The YAML structure must be as shown in the Examples bellow.
      - This inventory is meant to work in conjunction with the
        [YAML Inventory](https://github.com/jtyr/ansible-yaml_inventory).
    notes:
      - The YAML Inventory defines the group structure.
      - The YAML List inventory defines the individual hosts and their
        assignment to individual groups.
    options:
      group_key:
        description:
          - Name of the key which defines the group assignment.
        default: ansible.group
      add_inv_var:
        description:
          - Whether to add all data keys/values as an invengory variable.
        type: bool
        default: yes
      inv_var_key:
        description:
          - Key under which to add all data keys/values as an invengory
            variable.
        default: yaml_list
      data_file:
        description:
          - Path to the data YAML file.
        required: yes
      ungrouped_name:
        description:
          - Group name to which assign hosts without group.
        default: ungrouped_hosts
      accept:
        description:
          - List of conditions which make the record to be accepted. Empty
            list means to accept all. Each list item is a dictionary of
            key/value pairs of an item from the C(data_file). The value can
            start with C(~) indicating that the value represents a regular
            expression. It can also start with C(!) indicating negation of the
            value or regular expression. Don't use negative regular expression,
            negate regular expression with the C(!) instead.
          - Relations between individual items of the list is logical OR.
          - Relations between individual keys of the list item is logical AND.
          - The C(accept) conditions are evaluated before C(ignore) conditions.
        type: list
        default: []
      ignore:
        description:
          - List of conditions which make the record to be ignored. Empty
            list means to ignore nothing. Each list item is a dictionary of
            key/value pairs of an item from the C(data_file).
          - Relations between individual items of the list is logical OR.
          - Relations between individual keys of the list item is logical AND.
          - The C(ignore) conditions are evaluated after C(accept) conditions.
        type: list
        default: []
      optional_key_prefix:
        description:
          - Prefix which can be used for keys of individual conditions in the
            C(accept) and C(ignore) lists. A key prepended by this prefix is
            optional and its absence will not invalidate the rest of the
            condition.
        default: _
      grouping:
        description:
          - Dictionary of groups and their conditions. The key of the
            dictionary is the name of the group to be created. The value of the
            key is the list of conditions which needs to be satisfied to
            associate the group with the record. The condition list is the same
            like the C(accept) list.
        type: dict
        default: {}
      vars:
        description:
          - Dictionary of variables to be added to every host.
        type: dict
        default: {}
'''

EXAMPLES = '''
# Example of the config file
# (the lines commented out are optional)
plugin: yaml_list
data_file: /path/to/the/data_file.yaml
#group_key: ansible_group
#ungrouped_name: ungrouped_hosts
# Accept hosts which have 'uuid' value ending with 'a'
#accept:
#  - vcenter.uuid: ~.*a$
# Ignore all hosts which have 'state' equal to 'poweredOff' OR have their 'ip'
# not set OR have 'guest_id' value starting with 'win' AND also 'group' key
# doesn't exists or its value doesn't contain 'mygroup'
#ignore:
#  - state: poweredOff
#  - ip: null
#  - guest_id: ~^win.*
#    _ansible.group: "!~.*mygroup"
# Add all hosts having 'guest_id' value starting with 'win' into the 'windows'
# group
#grouping:
#  windows:
#    - vcenter.guest_id: ~^win
# Add inventory variable 'type: vm' to every host
#vars:
#  type: vm

#
# Example of the data file content
# (only the key 'name' is requered, the rest is optional)
#
# Add host into the default group (the ungrouped_name key in source file) and
# also into the 'jenkins' and 'team1' groups.
- ansible:
    group:
      - jenkins
      - team1
  ip: 192.168.1.102
  name: dc1-prd-jenkins01
  state: poweredOn
  vcenter:
    guest_id: centos64Guest
    uuid: 3ef61642-a703-7b25-d28a-d445487bc19a
# Add the host only into the 'rpd' group, don't add it into the default group
# (the ungrouped_name key in source file) at all.
- ansible:
    group: rdp
    override_ungrouped: yes
  ip: 192.168.1.12
  name: dc1-prd-rdp03
  state: poweredOff
  vcenter:
    guest_id: windows8Server64Guest
    uuid: 321460b2-2750-52a7-3bc4-0f12526960b7
- ip: null
  name: dc1-qa-data02
  state: poweredOff
  vcenter:
    guest_id: centos64Guest
    uuid: 52153396-f7b4-4038-6f00-e16ab5481d79
- name: dc1-qa-data03
'''


from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.inventory import BaseFileInventoryPlugin

import yaml
import re


class InventoryModule(BaseFileInventoryPlugin):
    NAME = 'yaml_list'
    created_groups = []

    def __init__(self):
        super(InventoryModule, self).__init__()

    def verify_file(self, path):
        valid = False

        if super(InventoryModule, self).verify_file(path):
            # Accept only files with specific extension
            if path.endswith(('.list.yaml', '.list.yml')):
                valid = True

        return valid

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path)

        config_data = self._read_config_data(path)

        # set_options from config data
        self._consume_options(config_data)

        data_file = self.get_option('data_file')

        # Parse the YAML file
        try:
            data = yaml.safe_load(self._read_yaml_file(data_file))
        except yaml.YAMLError as e:
            raise AnsibleParserError(
                "Unable parse inventory '%s': %s" % (data_file, e))

        group_key = self.get_option('group_key')

        # Add individual hosts
        for host in data:
            # Check if we want to accept this host
            if (
                    not self._eval_conditions(
                        host, self.get_option('accept')) or
                    self._eval_conditions(
                        host, self.get_option('ignore'), False)):
                continue

            # Don't add the same host twice
            if host['name'] in self.inventory.hosts:
                self.display.warning(
                    "Host '%s' is defined twice." % host['name'])

                continue

            # Override the default group if requested
            if (
                    'ansible' in host and
                    'override_ungrouped' in host['ansible'] and
                    host['ansible']['override_ungrouped'] is True):
                groups = []
            else:
                groups = [self.get_option('ungrouped_name')]

            # Check if the group_key exists in the host
            gk_exists, gk_v = self._get_host_key_value(host, group_key)

            # Check if host has associated group(s)
            if gk_exists:
                if isinstance(gk_v, list):
                    groups += gk_v
                else:
                    if ',' in gk_v:
                        groups += map(lambda x: x.strip(), gk_v.split(','))
                    else:
                        groups += [gk_v]

            # Add the host into each of the groups
            for group in groups:
                if group != '':
                    self._create_group(group)
                    self.inventory.add_host(host['name'], group)

                    inventory_vars = {}

                    # Add ansible_host variable
                    if 'ip' in host and host['ip'] is not None:
                        self.inventory.set_variable(
                            host['name'], 'ansible_host', host['ip'])

                    # Add inventory-wide variables
                    for k, v in self.get_option('vars').items():
                        inventory_vars[k] = v

                    # Add all host data as inventory vars
                    if self.get_option('add_inv_var'):
                        for k, v in host.items():
                            # Ignore 'ip' and 'name' keys
                            if k not in ['ip', 'name']:
                                # Make all `ansible.ansible_*` top facts
                                if k == 'ansible':
                                    for ak, av in v.items():
                                        if ak.startswith('ansible_'):
                                            inventory[ak] = av

                                inventory_vars[k] = v

                    # Set the inventory variable
                    self.inventory.set_variable(
                        host['name'],
                        self.get_option('inv_var_key'),
                        inventory_vars)

            # Apply grouping
            for group, conditions in self.get_option('grouping').items():
                if self._eval_conditions(host, conditions):
                    self._create_group(group)
                    self.inventory.add_host(host['name'], group)

    def _get_host_key_value(self, host, key):
        hk_exists = False
        h_v = None

        path = key.split('.')

        # Test the path
        for p in path:
            # Test if the path is a ref to a list's item
            m = re.match(r'(.*)\[(\d+)\]$', p)
            idx = None

            if m is not None and len(m.groups()) == 2:
                p = m.group(1)
                idx = int(m.group(2))

            if p in host:
                host = host[p]

                if idx is not None:
                    if isinstance(host, list) and len(host) > abs(idx):
                        host = host[idx]
                    else:
                        break
            else:
                break
        else:
            # This gets applied only when loop succesfully finished
            h_v = host
            hk_exists = True

        return hk_exists, h_v

    def _eval_conditions(self, host, conditions, default=True):
        self.display.debug("Starting %s" % ('accept' if default else 'ignore'))
        self.display.debug("Data: %s" % host)

        if len(conditions) == 0:
            ret = default
        else:
            ret = False

        # Loop through all conditions
        for c in conditions:
            i = 0
            c_len = len(c.items())

            # Loop through all keys/values of teach condition
            for k, v in c.items():
                i += 1
                optional = False
                neg = False

                # Check if the key is optional
                if k.startswith(self.get_option('optional_key_prefix')):
                    k = k[1:]
                    optional = True

                # Check if the value is negation
                if v is not None and v.startswith('!'):
                    neg = True

                # Check if the key exists in the host
                hk_exists, h_v = self._get_host_key_value(host, k)

                if hk_exists:
                    # If the key exists, normalize the value
                    if isinstance(h_v, list):
                        h_vals = h_v
                    else:
                        h_vals = [h_v]

                    neg_ret = True

                    # Loop through all value items
                    for h_val in h_vals:
                        self.display.debug(
                            "  Key '%s' exists - comparing condition %s=%s "
                            "with value %s" % (k, k, v, h_val))

                        # Compare the host value with the condition value
                        if v is None:
                            if h_val is None:
                                self.display.debug("    Matched None value")

                                ret = True
                            else:
                                self.display.debug("    Nothing matches None")

                                ret = False
                                neg_ret = False
                        elif h_val is not None:
                            if (
                                    v.startswith('!~') and
                                    re.match(v[2:], h_val) is not None):
                                self.display.debug(
                                    "    Matched negative regexp value")

                                ret = False
                                neg_ret = False
                            elif (
                                    v.startswith('~') and
                                    re.match(v[1:], h_val) is not None):
                                self.display.debug("    Matched regexp value")

                                ret = True
                            elif (
                                    v.startswith('!') and
                                    h_val == v[1:]):
                                self.display.debug(
                                    "    Matched negative value")

                                ret = False
                                neg_ret = False
                            elif h_val == v:
                                self.display.debug("    Matched value")

                                ret = True
                            else:
                                self.display.debug("    Nothing matches")

                                ret = False
                                neg_ret = True
                        else:
                            self.display.debug(
                                "    Nothing matches (should not happen)")

                            ret = False
                            neg_ret = False

                        if not neg_ret:
                            self.display.debug(
                                "  <- Breaking value loop because net_reg is "
                                "False")

                            ret = neg_ret

                            break
                        elif not neg and ret:
                            self.display.debug(
                                "  <- Breaking value loop because cond is "
                                "True")

                            break
                    if neg:
                        self.display.debug("  <- Taking net_reg value")

                        ret = neg_ret
                elif optional:
                    self.display.debug("  Key '%s' is optional" % k)

                    if i < c_len:
                        ret = True
                else:
                    self.display.debug("  Key '%s' does not exist" % k)

                    ret = False

                if not ret:
                    self.display.debug(
                        "  <- Breaking key loop because one of the values "
                        "turn ret=False")

                    break
            if ret:
                self.display.debug("  <- Breaking cond loop because ret=True")

                break

        self.display.debug(
            "Finishing %s with ret=%s" % (
                ('accept' if default else 'ignore'),
                ret))

        return ret

    def _create_group(self, group):
        if group not in self.created_groups:
            self.inventory.add_group(group)
            self.created_groups.append(group)

    def _read_yaml_file(self, path):
        # Custom method to read the content of the YAML file
        content = ''

        try:
            f = open(path, 'r')
        except IOError as e:
            raise AnsibleError("E: Cannot open file '%s'.\n%s" % (path, e))

        for line in f.readlines():
            content += line

        try:
            f.close()
        except IOError as e:
            raise AnsibleError("E: Cannot close file '%s'.\n%s" % (path, e))

        return content
