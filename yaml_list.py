from __future__ import (absolute_import, division, print_function)
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.inventory import BaseFileInventoryPlugin

import yaml
import re

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
        default: ansible_group
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
#  - uuid: ~.*a$
# Ignore all hosts which have 'state' equal to 'poweredOff' OR have their 'ip'
# not set OR have 'guest_id' value starting with 'win' AND also 'group' key
# doesn't exists or its value doesn't contain 'mygroup'
#ignore:
#  - state: poweredOff
#  - ip: null
#  - guest_id: ~^win.*
#    _ansible_group: !~.*mygroup
# Add all hosts having 'guest_id' value starting with 'win' into the 'windows'
# group
#grouping:
#  windows:
#    - guest_id: ~^win

#
# Example of the data file content
# (only the key 'name' is requered, the rest is optional)
#
# Add host into the default group (the ungrouped_name key in source file) and
# also into the 'jenkins' and 'team1' groups.
- ansible_group:
    - jenkins
    - team1
  guest_id: centos64Guest
  ip: 192.168.1.102
  name: aws-prd-jenkins01
  state: poweredOn
  uuid: 3ef61642-a703-7b25-d28a-d445487bc19a
# Add the host only into the 'rpd' group, don't add it into the default group
# (the ungrouped_name key in source file) at all.
- ansible_group: rdp
  override_ungrouped: yes
  guest_id: windows8Server64Guest
  ip: 192.168.1.12
  name: aws-prd-rdp03
  state: poweredOff
  uuid: 321460b2-2750-52a7-3bc4-0f12526960b7
- guest_id: centos64Guest
  ip: null
  name: aws-qa-data02
  state: poweredOff
  uuid: 52153396-f7b4-4038-6f00-e16ab5481d79
- name: aws-qa-data03
'''


class InventoryModule(BaseFileInventoryPlugin):
    NAME = 'yaml_list'
    created_groups = []

    def __init__(self):
        super(InventoryModule, self).__init__()

    def verify_file(self, path):
        valid = False

        if super(InventoryModule, self).verify_file(path):
            # Accept only files with specific extension
            if path.endswith(('.ext.yaml', '.ext.yml')):
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
                    'override_ungrouped' in host and
                    host['override_ungrouped'] is True):
                groups = []
            else:
                groups = [self.get_option('ungrouped_name')]

            # Check if host has associated group(s)
            if group_key in host:
                group_key_v = host[group_key]

                if isinstance(group_key_v, list):
                    groups += group_key_v
                else:
                    if ',' in group_key_v:
                        groups += map(
                            lambda x: x.strip(), group_key_v.split(','))
                    else:
                        groups += [group_key_v]

            # Add the host into each of the groups
            for group in groups:
                if group != '':
                    self._create_group(group)
                    self.inventory.add_host(host['name'], group)

                    # Add ansible_host variable
                    if 'ip' in host and host['ip'] is not None:
                        self.inventory.set_variable(
                            host['name'], 'ansible_host', host['ip'])

                    # Add all data keys/values as an inventory var
                    if self.get_option('add_inv_var'):
                        inventory_vars = {}

                        for k, v in host.items():
                            # Ignore 'ip' and 'name' keys
                            if k not in ['ip', 'name']:
                                inventory_vars[k] = v

                        self.inventory.set_variable(
                            host['name'],
                            self.get_option('inv_var_key'),
                            inventory_vars)

            # Apply grouping
            for group, conditions in self.get_option('grouping').items():
                if self._eval_conditions(host, conditions):
                    self._create_group(group)
                    self.inventory.add_host(host['name'], group)

    def _eval_conditions(self, host, conditions, default=True):
        ret = False

        if len(conditions) == 0:
            ret = default

        for c in conditions:
            i = 0
            c_len = len(c.items())

            for k, v in c.items():
                i += 1
                optional = False
                neg = False

                if k.startswith(self.get_option('optional_key_prefix')):
                    k = k[1:]
                    optional = True

                if v is not None and v.startswith('!'):
                    neg = True

                if k in host:
                    if isinstance(host[k], list):
                        h_vals = host[k]
                    else:
                        h_vals = [host[k]]

                    neg_ret = True

                    for h_val in h_vals:
                        if v is None:
                            if h_val is None:
                                # Matched None value
                                ret = True
                            else:
                                # Nothing matches
                                ret = False
                                neg_ret &= False
                        elif h_val is not None:
                            if (
                                    v.startswith('!~') and
                                    re.match(v[2:], h_val) is None):
                                # Matched negative regexp value
                                ret = True
                            elif (
                                    v.startswith('~') and
                                    re.match(v[1:], h_val) is not None):
                                # Matched regexp value
                                ret = True
                            elif (
                                    v.startswith('!') and
                                    h_val == v[1:]):
                                # Matched negative value
                                ret = True
                            elif h_val == v:
                                # Matched value
                                ret = True
                            else:
                                # Nothing matches
                                ret = False
                                neg_ret &= False
                        else:
                            # Nothing matches
                            ret = False
                            neg_ret &= False

                        if not neg and ret:
                            # Breaking list loop because cond is True
                            break

                    if neg:
                        ret = neg_ret
                elif optional:
                    # Key is optional
                    if i < c_len:
                        # The condition item is not last
                        ret = True
                else:
                    # Key does not exist
                    ret = False

                if not ret:
                    # Breaking because one of the cond keys is False
                    break

            if ret:
                # Breaking because cond is True
                break

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
