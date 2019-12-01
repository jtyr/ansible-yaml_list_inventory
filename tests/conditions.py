import os
import unittest
import yaml
from ansible import constants as C
from yaml_list import InventoryModule


class MyInventoryModule(InventoryModule):
    def get_option(self, key):
        # Override for 'optional_key_prefix'
        return '_'


class MyTestCase(unittest.TestCase):
    def _getenvbool(self, name, default):
        val = os.getenv(name)

        if val is None:
            ret = default
        elif val in ('1', 'yes', 'YES'):
            ret = True
        else:
            ret = False

        return ret

    def _parse_yaml_file(self, data_file):
        im = MyInventoryModule()

        try:
            data = yaml.safe_load(im._read_yaml_file(data_file))
        except yaml.YAMLError as e:
            raise Exception(
                "Unable parse inventory '%s': %s" % (data_file, e))

        return data

    def _test(self, host, accept=[], ignore=[], grouping={}, expected=True):
        C.DEFAULT_DEBUG = self._getenvbool('DEBUG', False)
        C.COLOR_DEBUG = 'normal'

        im = MyInventoryModule()

        if (
                im._eval_conditions(host, accept) and
                not im._eval_conditions(host, ignore, False)):
            im.display.debug('!!! Adding !!!')

            result = True

            for group, conditions in grouping.items():
                if self._eval_conditions(host, conditions):
                    im.display.debug("!!! Adding into group %s" % group)
        else:
            im.display.debug('!!! NOT adding !!!')

            result = False

        im.display.debug('-----------')

        if expected:
            self.assertTrue(result)
        else:
            self.assertFalse(result)


class Test(MyTestCase):
    def test_empty(self):
        self._test(None, expected=True)

    def test_equal(self):
        host = {
            'name': 'test',
        }
        conditions = [
            {
                'accept': [
                    {
                        'name': 'test',
                    }
                ],
                'ignore': [],
                'expected': True,
            }, {
                'accept': [],
                'ignore': [
                    {
                        'name': 'test',
                    }
                ],
                'expected': False,
            }, {
                'accept': [
                    {
                        'name': '!test',
                    }
                ],
                'ignore': [],
                'expected': False,
            }, {
                'accept': [],
                'ignore': [
                    {
                        'name': '!test',
                    }
                ],
                'expected': True,
            },
        ]

        for i, c in enumerate(conditions):
            with self.subTest(i=i):
                self._test(
                    host,
                    accept=c['accept'],
                    ignore=c['ignore'],
                    expected=c['expected'])

    def test_regexp(self):
        host = {
            'name': 'test',
        }
        conditions = [
            {
                'accept': [
                    {
                        'name': '~^test',
                    }
                ],
                'ignore': [],
                'expected': True,
            }, {
                'accept': [],
                'ignore': [
                    {
                        'name': '~^test',
                    }
                ],
                'expected': False,
            }, {
                'accept': [
                    {
                        'name': '!~^test',
                    }
                ],
                'ignore': [],
                'expected': False,
            }, {
                'accept': [],
                'ignore': [
                    {
                        'name': '!~^test',
                    }
                ],
                'expected': True,
            },
        ]

        for i, c in enumerate(conditions):
            with self.subTest(i=i):
                self._test(
                    host,
                    accept=c['accept'],
                    ignore=c['ignore'],
                    expected=c['expected'])

    def test_ignore_ip_state(self):
        data = [
            {
                'name': 'test',
                'state': 'poweredOn',
                'ip': '1.2.3.4',
                'expected': True,
            }, {
                'name': 'test',
                'state': 'poweredOff',
                'ip': '1.2.3.4',
                'expected': False,
            }, {
                'name': 'test',
                'state': 'poweredOn',
                'ip': None,
                'expected': False,
            }, {
                'name': 'test',
                'state': 'poweredOff',
                'ip': None,
                'expected': False,
            },
        ]
        ignore = [
            {
                'ip': None,
            }, {
                'state': 'poweredOff'
            }
        ]

        for i, host in enumerate(data):
            with self.subTest(i=i, ip=host['ip'], state=host['state']):
                self._test(host, ignore=ignore, expected=host['expected'])

    def test_ignore_ip_state_guest_group(self):
        data = [
            {
                'name': 'test',
                'state': 'poweredOn',
                'ip': '1.2.3.4',
                'guest_id': 'windows8Server64Guest',
                'ansible_group': 'aaa',
                'expected': False,
            }, {
                'name': 'test',
                'state': 'poweredOn',
                'ip': '1.2.3.4',
                'guest_id': 'windows8Server64Guest',
                'ansible_group': 'bbb',
                'expected': True,
            }, {
                'name': 'test',
                'state': 'poweredOn',
                'ip': '1.2.3.4',
                'guest_id': 'windows8Server64Guest',
                'ansible_group': ['000', 'aaa', 'zzz'],
                'expected': False,
            }, {
                'name': 'test',
                'state': 'poweredOn',
                'ip': '1.2.3.4',
                'guest_id': 'windows8Server64Guest',
                'ansible_group': ['000', 'bbb', 'zzz'],
                'expected': True,
            }, {
                'name': 'test',
                'state': 'poweredOn',
                'ip': '1.2.3.4',
                'guest_id': 'windows8Server64Guest',
                'expected': False,
            },
        ]
        ignore = [
            {
                'ip': None,
            }, {
                'guest_id': 'windows8Server64Guest',
                '_ansible_group': '!bbb'
            }, {
                'state': 'poweredOff'
            }
        ]

        for i, host in enumerate(data):
            ag = None

            if 'ansible_group' in host:
                ag = host['ansible_group']

            with self.subTest(
                    i=i,
                    ip=host['ip'],
                    state=host['state'],
                    guest_id=host['guest_id'],
                    ansible_group=ag):
                self._test(host, ignore=ignore, expected=host['expected'])

    def test_complex_key(self):
        tests = [
            {
                'host': {
                    'name': 'test',
                    'vcenter': {
                        'guest_id': 'windows8Server64Guest',
                    },
                },
                'accept': [
                    {
                        'vcenter.guest_id': 'windows8Server64Guest',
                    }
                ],
                'expected': True,
            }, {
                'host': {
                    'name': 'test',
                    'guest_id': 'windows8Server64Guest',
                },
                'accept': [
                    {
                        'vcenter.guest_id': 'windows8Server64Guest',
                    }
                ],
                'expected': False,
            }, {
                'host': {
                    'name': 'test',
                    'vcenter': {
                        'nics': [
                            {
                                'name': 'eth0',
                                'mac': '11:22:33:44:55:66',
                            }, {
                                'name': 'eth1',
                                'mac': '22:33:44:55:66:11',
                            }
                        ],
                    },
                },
                'accept': [
                    {
                        'vcenter.nics[0].name': 'eth0',
                    }
                ],
                'expected': True,
            }, {
                'host': {
                    'name': 'test',
                    'vcenter': {
                        'nics': [
                            {
                                'name': 'eth0',
                                'mac': '11:22:33:44:55:66',
                            }, {
                                'name': 'eth1',
                                'mac': '22:33:44:55:66:11',
                            }
                        ],
                    },
                },
                'accept': [
                    {
                        'vcenter.nics[4].name': 'eth4',
                    }
                ],
                'expected': False,
            },
        ]

        for i, t in enumerate(tests):
            with self.subTest(i=i):
                self._test(
                    host=t['host'],
                    accept=t['accept'],
                    expected=t['expected'])

    def test_real(self):
        if not self._getenvbool('DEBUG', False):
            self.skipTest("No DEBUG defined.")

        host_filter = os.getenv('HOST')
        data_file = os.getenv('DATA')
        source_file = os.getenv('SOURCE')
        expected = int(os.getenv('EXPECTED', 1))

        if host_filter is None:
            raise Exception("No HOST defined!")

        if data_file is None:
            raise Exception("No DATA defined!")

        if source_file is None:
            raise Exception("No SOURCE defined!")

        data = self._parse_yaml_file(data_file)
        source = self._parse_yaml_file(source_file)
        host = None
        accept = []
        ignore = []

        if 'accept' in source:
            accept = source['accept']

        if 'ignore' in source:
            ignore = source['ignore']

        for h in data:
            if 'name' in h and h['name'] == host_filter:
                host = h

                break

        if host is None:
            raise Exception("No '%s' found in the data file!" % host_filter)

        self._test(host, accept=accept, ignore=ignore, expected=expected)


if __name__ == '__main__':
    unittest.main()
