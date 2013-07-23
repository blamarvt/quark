# Copyright 2013 Openstack Foundation
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
#  under the License.

import contextlib

import mock
from neutron.api.v2 import attributes as neutron_attrs
from neutron.common import exceptions
from neutron.extensions import securitygroup as sg_ext

from quark.db import api as quark_db_api
from quark.db import models
from quark.tests import test_quark_plugin


class TestQuarkGetPorts(test_quark_plugin.TestQuarkPlugin):
    @contextlib.contextmanager
    def _stubs(self, ports=None, addrs=None):
        port_models = []
        addr_models = None
        if addrs:
            addr_models = []
            for address in addrs:
                a = models.IPAddress()
                a.update(address)
                addr_models.append(a)

        if isinstance(ports, list):
            for port in ports:
                port_model = models.Port()
                port_model.update(port)
                if addr_models:
                    port_model.ip_addresses = addr_models
                port_models.append(port_model)
        elif ports is None:
            port_models = None
        else:
            port_model = models.Port()
            port_model.update(ports)
            if addr_models:
                port_model.ip_addresses = addr_models
            port_models = port_model

        db_mod = "quark.db.api"
        with contextlib.nested(
            mock.patch("%s.port_find" % db_mod)
        ) as (port_find,):
            port_find.return_value = port_models
            yield

    def test_port_list_no_ports(self):
        with self._stubs(ports=[]):
            ports = self.plugin.get_ports(self.context, filters=None,
                                          fields=None)
            self.assertEqual(ports, [])

    def test_port_list_with_ports(self):
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.100",
                  subnet_id=1, network_id=2, version=4)
        port = dict(mac_address="aa:bb:cc:dd:ee:ff", network_id=1,
                    tenant_id=self.context.tenant_id, device_id=2)
        expected = {'status': None,
                    'device_owner': None,
                    'mac_address': 'aa:bb:cc:dd:ee:ff',
                    'network_id': 1,
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'device_id': 2}
        with self._stubs(ports=[port], addrs=[ip]):
            ports = self.plugin.get_ports(self.context, filters=None,
                                          fields=None)
            self.assertEqual(len(ports), 1)
            fixed_ips = ports[0].pop("fixed_ips")
            for key in expected.keys():
                self.assertEqual(ports[0][key], expected[key])
            self.assertEqual(fixed_ips[0]["subnet_id"], ip["subnet_id"])
            self.assertEqual(fixed_ips[0]["ip_address"],
                             ip["address_readable"])

    def test_port_show(self):
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.100",
                  subnet_id=1, network_id=2, version=4)
        port = dict(mac_address="AA:BB:CC:DD:EE:FF", network_id=1,
                    tenant_id=self.context.tenant_id, device_id=2)
        expected = {'status': None,
                    'device_owner': None,
                    'mac_address': 'AA:BB:CC:DD:EE:FF',
                    'network_id': 1,
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'device_id': 2}
        with self._stubs(ports=port, addrs=[ip]):
            result = self.plugin.get_port(self.context, 1)
            fixed_ips = result.pop("fixed_ips")
            for key in expected.keys():
                self.assertEqual(result[key], expected[key])
            self.assertEqual(fixed_ips[0]["subnet_id"], ip["subnet_id"])
            self.assertEqual(fixed_ips[0]["ip_address"],
                             ip["address_readable"])

    def test_port_show_with_int_mac(self):
        port = dict(mac_address=187723572702975L, network_id=1,
                    tenant_id=self.context.tenant_id, device_id=2)
        expected = {'status': None,
                    'device_owner': None,
                    'mac_address': 'aa:bb:cc:dd:ee:ff',
                    'network_id': 1,
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'fixed_ips': [],
                    'device_id': 2}
        with self._stubs(ports=port):
            result = self.plugin.get_port(self.context, 1)
            for key in expected.keys():
                self.assertEqual(result[key], expected[key])

    def test_port_show_not_found(self):
        with self._stubs(ports=None):
            with self.assertRaises(exceptions.PortNotFound):
                self.plugin.get_port(self.context, 1)


class TestQuarkCreatePort(test_quark_plugin.TestQuarkPlugin):
    @contextlib.contextmanager
    def _stubs(self, port=None, network=None, addr=None, mac=None):
        port_model = models.Port()
        port_model.update(port)
        port_models = port_model

        db_mod = "quark.db.api"
        ipam = "quark.ipam.QuarkIpam"
        with contextlib.nested(
            mock.patch("%s.port_create" % db_mod),
            mock.patch("%s.network_find" % db_mod),
            mock.patch("%s.allocate_ip_address" % ipam),
            mock.patch("%s.allocate_mac_address" % ipam),
        ) as (port_create, net_find, alloc_ip, alloc_mac):
            port_create.return_value = port_models
            net_find.return_value = network
            alloc_ip.return_value = addr
            alloc_mac.return_value = mac
            yield port_create

    def test_create_port(self):
        network = dict(id=1)
        mac = dict(address="aa:bb:cc:dd:ee:ff")
        port_name = "foobar"
        ip = dict()
        port = dict(port=dict(mac_address=mac["address"], network_id=1,
                              tenant_id=self.context.tenant_id, device_id=2,
                              name=port_name))
        expected = {'status': None,
                    'name': port_name,
                    'device_owner': None,
                    'mac_address': mac["address"],
                    'network_id': network["id"],
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'fixed_ips': [],
                    'device_id': 2}
        with self._stubs(port=port["port"], network=network, addr=ip,
                         mac=mac) as port_create:
            result = self.plugin.create_port(self.context, port)
            self.assertTrue(port_create.called)
            for key in expected.keys():
                self.assertEqual(result[key], expected[key])

    def test_create_port_mac_address_not_specified(self):
        network = dict(id=1)
        mac = dict(address="aa:bb:cc:dd:ee:ff")
        ip = dict()
        port = dict(port=dict(mac_address=mac["address"], network_id=1,
                              tenant_id=self.context.tenant_id, device_id=2))
        expected = {'status': None,
                    'device_owner': None,
                    'mac_address': mac["address"],
                    'network_id': network["id"],
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'fixed_ips': [],
                    'device_id': 2}
        with self._stubs(port=port["port"], network=network, addr=ip,
                         mac=mac) as port_create:
            port["port"]["mac_address"] = neutron_attrs.ATTR_NOT_SPECIFIED
            result = self.plugin.create_port(self.context, port)
            self.assertTrue(port_create.called)
            for key in expected.keys():
                self.assertEqual(result[key], expected[key])

    def test_create_port_fixed_ips(self):
        network = dict(id=1)
        mac = dict(address="aa:bb:cc:dd:ee:ff")
        ip = mock.MagicMock()
        ip.get = lambda x, *y: 1 if x == "subnet_id" else None
        ip.formatted = lambda: "192.168.10.45"
        fixed_ips = [dict(subnet_id=1, ip_address="192.168.10.45")]
        port = dict(port=dict(mac_address=mac["address"], network_id=1,
                              tenant_id=self.context.tenant_id, device_id=2,
                              fixed_ips=fixed_ips, ip_addresses=[ip]))
        expected = {'status': None,
                    'device_owner': None,
                    'mac_address': mac["address"],
                    'network_id': network["id"],
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'fixed_ips': fixed_ips,
                    'device_id': 2}
        with self._stubs(port=port["port"], network=network, addr=ip,
                         mac=mac) as port_create:
            result = self.plugin.create_port(self.context, port)
            self.assertTrue(port_create.called)
            for key in expected.keys():
                self.assertEqual(result[key], expected[key])

    def test_create_port_fixed_ips_bad_request(self):
        network = dict(id=1)
        mac = dict(address="aa:bb:cc:dd:ee:ff")
        ip = mock.MagicMock()
        ip.get = lambda x: 1 if x == "subnet_id" else None
        ip.formatted = lambda: "192.168.10.45"
        fixed_ips = [dict()]
        port = dict(port=dict(mac_address=mac["address"], network_id=1,
                              tenant_id=self.context.tenant_id, device_id=2,
                              fixed_ips=fixed_ips, ip_addresses=[ip]))
        with self._stubs(port=port["port"], network=network, addr=ip,
                         mac=mac):
            with self.assertRaises(exceptions.BadRequest):
                self.plugin.create_port(self.context, port)

    def test_create_port_no_network_found(self):
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2))
        with self._stubs(network=None, port=port["port"]):
            with self.assertRaises(exceptions.NetworkNotFound):
                self.plugin.create_port(self.context, port)

    def test_create_port_net_at_max(self):
        network = dict(id=1, ports=[models.Port()])
        mac = dict(address="aa:bb:cc:dd:ee:ff")
        port_name = "foobar"
        ip = dict()
        port = dict(port=dict(mac_address=mac["address"], network_id=1,
                              tenant_id=self.context.tenant_id, device_id=2,
                              name=port_name))
        with self._stubs(port=port["port"], network=network, addr=ip, mac=mac):
            with self.assertRaises(exceptions.OverQuota):
                self.plugin.create_port(self.context, port)

    def test_create_port_security_groups(self, groups=[1]):
        network = dict(id=1)
        mac = dict(address="aa:bb:cc:dd:ee:ff")
        port_name = "foobar"
        ip = dict()
        group = models.SecurityGroup()
        group.update({'id': 1, 'tenant_id': self.context.tenant_id,
                      'name': 'foo', 'description': 'bar'})
        port = dict(port=dict(mac_address=mac["address"], network_id=1,
                              tenant_id=self.context.tenant_id, device_id=2,
                              name=port_name, security_groups=[group]))
        expected = {'status': None,
                    'name': port_name,
                    'device_owner': None,
                    'mac_address': mac["address"],
                    'network_id': network["id"],
                    'tenant_id': self.context.tenant_id,
                    'admin_state_up': None,
                    'fixed_ips': [],
                    'security_groups': groups,
                    'device_id': 2}
        with self._stubs(port=port["port"], network=network, addr=ip,
                         mac=mac) as port_create:
            with mock.patch("quark.db.api.security_group_find") as group_find:
                group_find.return_value = (groups and group)
                port["port"]["security_groups"] = groups or [1]
                result = self.plugin.create_port(self.context, port)
                self.assertTrue(port_create.called)
                for key in expected.keys():
                    self.assertEqual(result[key], expected[key])

    def test_create_port_security_groups_not_found(self):
        with self.assertRaises(sg_ext.SecurityGroupNotFound):
            self.test_create_port_security_groups([])


class TestQuarkUpdatePort(test_quark_plugin.TestQuarkPlugin):
    @contextlib.contextmanager
    def _stubs(self, port):
        port_model = None
        if port:
            port_model = models.Port()
            port_model.update(port)
        with contextlib.nested(
            mock.patch("quark.db.api.port_find"),
            mock.patch("quark.db.api.port_update"),
            mock.patch("quark.ipam.QuarkIpam.allocate_ip_address"),
            mock.patch("quark.ipam.QuarkIpam.deallocate_ip_address")
        ) as (port_find, port_update, alloc_ip, dealloc_ip):
            port_find.return_value = port_model
            yield port_find, port_update, alloc_ip, dealloc_ip

    def test_update_port_not_found(self):
        with self._stubs(port=None):
            with self.assertRaises(exceptions.PortNotFound):
                self.plugin.update_port(self.context, 1, {})

    def test_update_port(self):
        with self._stubs(
            port=dict(id=1, name="myport")
        ) as (port_find, port_update, alloc_ip, dealloc_ip):
            new_port = dict(port=dict(name="ourport"))
            self.plugin.update_port(self.context, 1, new_port)
            self.assertEqual(port_find.call_count, 1)
            port_update.assert_called_once_with(
                self.context,
                port_find(),
                name="ourport",
                security_groups=[])

    def test_update_port_fixed_ip_bad_request(self):
        with self._stubs(
            port=dict(id=1, name="myport")
        ) as (port_find, port_update, alloc_ip, dealloc_ip):
            new_port = dict(port=dict(
                fixed_ips=[dict(subnet_id=None,
                                ip_address=None)]))
            with self.assertRaises(exceptions.BadRequest):
                self.plugin.update_port(self.context, 1, new_port)

    def test_update_port_fixed_ip(self):
        with self._stubs(
            port=dict(id=1, name="myport", mac_address="0:0:0:0:0:1")
        ) as (port_find, port_update, alloc_ip, dealloc_ip):
            new_port = dict(port=dict(
                fixed_ips=[dict(subnet_id=1,
                                ip_address="1.1.1.1")]))
            self.plugin.update_port(self.context, 1, new_port)
            self.assertEqual(dealloc_ip.call_count, 1)
            self.assertEqual(alloc_ip.call_count, 1)


class TestQuarkPostUpdatePort(test_quark_plugin.TestQuarkPlugin):
    @contextlib.contextmanager
    def _stubs(self, port, addr, addr2=None):
        port_model = None
        addr_model = None
        addr_model2 = None
        if port:
            port_model = models.Port()
            port_model.update(port)
        if addr:
            addr_model = models.IPAddress()
            addr_model.update(addr)
        if addr2:
            addr_model2 = models.IPAddress()
            addr_model2.update(addr2)
        with contextlib.nested(
            mock.patch("quark.db.api.port_find"),
            mock.patch("quark.ipam.QuarkIpam.allocate_ip_address"),
            mock.patch("quark.db.api.ip_address_find")
        ) as (port_find, alloc_ip, ip_find):
            port_find.return_value = port_model
            alloc_ip.return_value = addr_model2 if addr_model2 else addr_model
            ip_find.return_value = addr_model
            yield port_find, alloc_ip, ip_find

    def test_post_update_port_no_ports(self):
        with self.assertRaises(exceptions.PortNotFound):
            self.plugin.post_update_port(self.context, 1,
                                         {"port": {"network_id": 1}})

    def test_post_update_port_fixed_ips_empty_body(self):
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2))
        with self._stubs(port=port, addr=None):
            with self.assertRaises(exceptions.BadRequest):
                self.plugin.post_update_port(self.context, 1, {})
            with self.assertRaises(exceptions.BadRequest):
                self.plugin.post_update_port(self.context, 1, {"port": {}})

    def test_post_update_port_fixed_ips_ip(self):
        new_port_ip = dict(port=dict(fixed_ips=[dict()]))
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2))
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.100",
                  subnet_id=1, network_id=2, version=4, deallocated=True)
        with self._stubs(port=port, addr=ip) as (port_find, alloc_ip, ip_find):
            response = self.plugin.post_update_port(self.context, 1,
                                                    new_port_ip)
            self.assertEqual(port_find.call_count, 1)
            self.assertEqual(alloc_ip.call_count, 1)
            self.assertEqual(ip_find.call_count, 0)
            self.assertEqual(response["fixed_ips"][0]["ip_address"],
                             "192.168.1.100")

    def test_post_update_port_fixed_ips_ip_id(self):
        new_port_ip = dict(port=dict(fixed_ips=[dict(ip_id=1)]))
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2))
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.100",
                  subnet_id=1, network_id=2, version=4, deallocated=True)
        with self._stubs(port=port, addr=ip) as (port_find, alloc_ip, ip_find):
            response = self.plugin.post_update_port(self.context, 1,
                                                    new_port_ip)
            self.assertEqual(port_find.call_count, 1)
            self.assertEqual(alloc_ip.call_count, 0)
            self.assertEqual(ip_find.call_count, 1)
            self.assertEqual(response["fixed_ips"][0]["ip_address"],
                             "192.168.1.100")

    def test_post_update_port_fixed_ips_ip_address_exists(self):
        new_port_ip = dict(port=dict(fixed_ips=[dict(
            ip_address="192.168.1.100")]))
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2))
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.100",
                  subnet_id=1, network_id=2, version=4, deallocated=True)
        with self._stubs(port=port, addr=ip) as (port_find, alloc_ip, ip_find):
            response = self.plugin.post_update_port(self.context, 1,
                                                    new_port_ip)
            self.assertEqual(port_find.call_count, 1)
            self.assertEqual(alloc_ip.call_count, 0)
            self.assertEqual(ip_find.call_count, 1)
            self.assertEqual(response["fixed_ips"][0]["ip_address"],
                             "192.168.1.100")

    def test_post_update_port_fixed_ips_ip_address_doesnt_exist(self):
        new_port_ip = dict(port=dict(fixed_ips=[dict(
            ip_address="192.168.1.101")]))
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2))
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.101",
                  subnet_id=1, network_id=2, version=4, deallocated=True)
        with self._stubs(port=port, addr=None, addr2=ip) as \
                (port_find, alloc_ip, ip_find):
            response = self.plugin.post_update_port(self.context, 1,
                                                    new_port_ip)
            self.assertEqual(port_find.call_count, 1)
            self.assertEqual(alloc_ip.call_count, 1)
            self.assertEqual(ip_find.call_count, 1)
            self.assertEqual(response["fixed_ips"][0]["ip_address"],
                             "192.168.1.101")


class TestQuarkGetPortCount(test_quark_plugin.TestQuarkPlugin):
    def test_get_port_count(self):
        """This isn't really testable."""
        with mock.patch("quark.db.api.port_count_all"):
            self.plugin.get_ports_count(self.context, {})


class TestQuarkDeletePort(test_quark_plugin.TestQuarkPlugin):
    @contextlib.contextmanager
    def _stubs(self, port=None, addr=None, mac=None):
        port_models = None
        if port:
            port_model = models.Port()
            port_model.update(port)
            port_models = port_model

        db_mod = "quark.db.api"
        ipam = "quark.ipam.QuarkIpam"
        with contextlib.nested(
            mock.patch("%s.port_find" % db_mod),
            mock.patch("%s.deallocate_ip_address" % ipam),
            mock.patch("%s.deallocate_mac_address" % ipam),
            mock.patch("%s.port_delete" % db_mod),
            mock.patch("quark.drivers.base.BaseDriver.delete_port")
        ) as (port_find, dealloc_ip, dealloc_mac, db_port_del,
              driver_port_del):
            port_find.return_value = port_models
            dealloc_ip.return_value = addr
            dealloc_mac.return_value = mac
            yield db_port_del, driver_port_del

    def test_port_delete(self):
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2, mac_address="AA:BB:CC:DD:EE:FF",
                              backend_key="foo"))
        with self._stubs(port=port["port"]) as (db_port_del, driver_port_del):
            self.plugin.delete_port(self.context, 1)
            self.assertTrue(db_port_del.called)
            driver_port_del.assert_called_with(self.context, "foo")

    def test_port_delete_port_not_found_fails(self):
        with self._stubs(port=None) as (db_port_del, driver_port_del):
            with self.assertRaises(exceptions.PortNotFound):
                self.plugin.delete_port(self.context, 1)


class TestQuarkDisassociatePort(test_quark_plugin.TestQuarkPlugin):
    @contextlib.contextmanager
    def _stubs(self, port=None):
        port_models = None
        if port:
            port_model = models.Port()
            port_model.update(port)
            for ip in port["fixed_ips"]:
                port_model.ip_addresses.append(models.IPAddress(
                    id=1,
                    address=ip["ip_address"],
                    subnet_id=ip["subnet_id"]))
            port_models = port_model

        db_mod = "quark.db.api"
        with mock.patch("%s.port_find" % db_mod) as port_find:
            port_find.return_value = port_models
            yield port_find

    def test_port_disassociate_port(self):
        ip = dict(id=1, address=3232235876, address_readable="192.168.1.100",
                  subnet_id=1, network_id=2, version=4)
        fixed_ips = [{"subnet_id": ip["subnet_id"],
                      "ip_address": ip["address_readable"]}]
        port = dict(port=dict(network_id=1, tenant_id=self.context.tenant_id,
                              device_id=2, mac_address="AA:BB:CC:DD:EE:FF",
                              backend_key="foo", fixed_ips=fixed_ips))
        with self._stubs(port=port["port"]) as (port_find):
            new_port = self.plugin.disassociate_port(self.context, 1, 1)
            port_find.assert_called_with(self.context,
                                         id=1,
                                         ip_address_id=[1],
                                         scope=quark_db_api.ONE)
            self.assertEqual(new_port["fixed_ips"], [])

    def test_port_disassociate_port_not_found_fails(self):
        with self._stubs(port=None):
            with self.assertRaises(exceptions.PortNotFound):
                self.plugin.disassociate_port(self.context, 1, 1)
