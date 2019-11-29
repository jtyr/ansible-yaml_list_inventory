YAML List inventory plugin
==========================

Anible Inventory Plugin reading YAML file containing hosts as a list of
key-value pairs. The YAML file can be produced manually or by a script. The
advantage is that the inventory is fast and the YAML files can be audited
in a source control system like Git.


Installation
------------

```shell
# Create basic directory structure
mkdir -p {tools,plugins/inventory,inventory_{data,sources}}

# Get the code and put the plugin into a specific directory
git clone https://github.com/jtyr/ansible-yaml_list_inventory tools/yaml_list_inventory
ln -s tools/yaml_list_inventory/yaml_list.py plugins/inventory/

# Add the plugin path and the intentory plugin into the config file
cat <<END >> ansible.cfg
[defaults]
# Specify path to the directory with all inventory plugins
inventory_plugins = plugins/inventory

[inventory]
# Enable only some inventory plugins
enable_plugins = script, yaml_list, host_list, ini
END
```


Usage
-----

Create a config file for the plugin (`inventory_sources/prd.ext.yaml`):

```yaml
---

plugin: yaml_list
data_file: inventory_data/prd.yaml
ungrouped_name: production
# Key name specifying Ansible groups
#group_key: ansible_group
# Accept hosts which have 'uuid' value ending with 'a'
accept:
  - uuid: ~.*a$
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
grouping:
  windows:
    - guest_id: ~^win
# Add inventory variable 'type: vm' to every host
vars:
  type: vm
```

Create data file (`inventory_data/prd.yaml`). The following example is
generated with a script reading the list of VMs from vCenter:

```yaml
---

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
# Put the host only into the 'rpd' group, don't put it into the default group
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
```

Run Ansible:

```shell
ansible-playbook -i inventory_sources site.yaml
```


Testing
-------

Tun unit tests:

```shell
# All unit tests
python3 -m unittest tests.conditions
python3 -m unittest tests.conditions.Test

# Specific unit test
python3 -m unittest tests.conditions.Test.test_equal

# Specific unit test with debug output
DEBUG=1 python3 -m unittest tests.conditions.Test.test_equal
```

Test a specific host with specific data and source files:

```shell
HOST='aws-prd-jenkins01'
DATA='path/to/my/inventory_data/prd.yaml'
SOURCE='path/to/my/inventory_sources/prd.ext.yaml'
DEBUG='1'
python3 -m unittest tests.conditions.Test.test_real
```


`yamllistctl.py`
----------------

This script allows to search, add or remove record from the YAML List inventory
data file.

```shell
# Search
./yamllistctl.py -d -f inventory_data/prd.yaml search aws-dev-test03

# Add host
./yamllistctl.py -d -f inventory_data/prd.yaml add aws-dev-test03 192.168.1.123

# Add host and set a group
./yamllistctl.py -d -f inventory_data/prd.yaml add aws-dev-test03 192.168.1.123 mygroup1

# Add host and set groups
./yamllistctl.py -d -f inventory_data/prd.yaml add aws-dev-test03 192.168.1.123 mygroup1,mygroup2

# Add host, set groups and set override_ungrouped
./yamllistctl.py -d -f inventory_data/prd.yaml add -o aws-dev-test03 192.168.1.123 mygroup1,mygroup2

# Remove host
./yamllistctl.py -d -f inventory_data/prd.yaml remove aws-dev-test03
```


License
-------

MIT


Author
------

Jiri Tyr
