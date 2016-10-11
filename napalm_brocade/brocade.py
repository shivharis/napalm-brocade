#
# Copyright 2016 Shiv Haris, Brocade Communication Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

"""
Brocade-Napalm Driver.

This driver is meant for SLX and NOS based switches.
"""
from netmiko import ConnectHandler
from napalm_base import helpers
from napalm_base.base import NetworkDriver
from napalm_base.exceptions import ConnectionException, MergeConfigException, \
    ReplaceConfigException, SessionLockedException, CommandErrorException

import os
import pdb
import re
from shutil import copyfile
from napalm_brocade.nos.nosdriver import NOSdriver as nosdriver

import pprint

# TBD(shh) Put this in config file (oslo_config)
EXPORT_HOST = "10.24.88.6"
EXPORT_USER = "shh"
EXPORT_PASSWORD = "ss"

pp = pprint.PrettyPrinter(indent=4)

class BrocadeDriver(NetworkDriver):
    """Napalm Driver for Vendor Brocade."""

    def __init__(self, hostname, username, password, timeout=60,
                 optional_args=None):
        """
        CTOR for the device.
        """

        if optional_args is None:
            optional_args = {}

        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.port = optional_args.get('port', 22)


    def open(self):
        """Open a connection to the device."""
        try:
            self.device = ConnectHandler(device_type='brocade_vdx',
                                         ip=self.hostname,
                                         port=self.port,
                                         username=self.username,
                                         password=self.password,
                                         timeout=self.timeout)
        except Exception:
            raise ConnectionException("Cannot connect to switch: %s:%s" \
                                          % (self.hostname, self.port))

    def close(self):
        """Close the connection to the device."""
        self.device.disconnect()

    def cli(self, commands=None):
        """
        Execute a list of commands and return the output in a dictionary format using the
        command as the key.

        """
        cli_output = dict()

        if not isinstance(commands, list):
            raise TypeError('Please enter a valid list of commands!')

        for command in commands:
            output = self.device.send_command(command)
            if 'Invalid input detected' in output:
                raise ValueError(
                    'Unable to execute command "{}"'.format(command))
            cli_output.setdefault(command, {})
            cli_output[command] = output

        return cli_output

    def send_command(self, cmd):
        """Send the cmd to the switch for execution."""
        output = self.device.send_command(cmd)
        if 'Invalid input detected' in output:
            raise ValueError('Unable to execute command "{}"'.format(cmd))
        return output

    def get_environment(self):

        environment = dict()

        environment['cpu'] = dict()
        environment['available_ram'] = ''
        environment['used_ram'] = ''

        cmd = 'show environment fan'
        output = self.device.send_command(cmd)
        lines = output.splitlines()

        fans = dict()
        for line in lines:
            fan = dict()
            regex = r'^Fan (.*) is (.*),.*$'
            match = re.search(regex, line)
            if match:
                fanindex = match.group(1)
                fan['status'] = match.group(2) == "Ok"
                fans[fanindex] = fan


        environment['fans'] = fans

        cmd = 'show environment power'
        output = self.device.send_command(cmd)
        lines = output.splitlines()
        lines = lines[1:-1]

        powers = dict()
        for line in lines:
            power = dict()
            regex = r'^Power Supply #(.*) is (.*)$'
            match = re.search(regex, line)
            if match:
                powerindex = match.group(1)
                power['status'] = match.group(2) == "OK"
                powers[powerindex] = power

        environment['power'] = powers

        cmd = 'show environment temp'
        output = self.device.send_command(cmd)
        lines = output.splitlines()
        lines = lines[3:-1]

        temps = dict()
        for line in lines:
            temp = dict()
            vals = line.split()
            if len(vals) == 4:
                tempindex = vals[0]
                temp['temperature'] = vals[2]
                temp['is_alert'] = vals[1] != "Ok"
                temp['is_critical'] = vals[1] != "Ok"
                temps[tempindex] = temp

        environment['temperature'] = temps

        cpu_cmd = 'show process cpu'

        output = self.device.send_command(cpu_cmd)
        output = output.strip()

        lines = output.splitlines()

        # cpus = dict()
        # while True:
        # line = lines.pop(0)
        # if 'Realtime Statistics' in line:
        # line = lines.pop(0)
        # cpu_regex = r'^.*One minute: (\d+\.\d+); Five.*$'
        # match = re.search(cpu_regex, line)
        # if match:
        # environment['cpu'][0]['%load'] = float(match.group(1))
        # 
        # 
        return environment

    def get_facts(self):
        cmd = "show system"
        fact_table = {}
        output = self.device.send_command(cmd)
        output = output.split('\n')
        output = output[3:-1]

        fact_table["vendor"] = "Brocade"
        fact_table["seriel_number"] = "xxxxx"

        for line in output:
            if len(line) == 0:
                return {}

            match = re.search("Up Time.*: up (.*)$", line)
            if match:
                uptime = match.group(1)
                fact_table["uptime"] = uptime

            match = re.search("^(.*) Version.*: (.*)$", line)
            if match:
                os_type = match.group(1)
                os_version = match.group(2)
                # fact_table["os_type"] = os_type
                fact_table["model"] = os_type
                fact_table["os_version"] = os_version

            match = re.search("^Management IP.*: (.*)$", line)
            if match:
                mgmt_ip = match.group(1)
                fact_table["hostname"] = mgmt_ip
                fact_table["fqdn"] = mgmt_ip

        return fact_table

    def get_vlan_table(self):
        """
        Get VLAN table.
        """
        vlan_table = []

        vlan_cmd = 'show vlan brief'
        output = self.device.send_command(vlan_cmd)
        output = output.split('\n')

        # Skip the first two lines which is the header
        output = output[5:-1]

        for line in output:
            if len(line) == 0:
                continue

            vlans = line.split()
            entry = {
                'vlan': vlans[0],
                'name': vlans[1]
                }
            vlan_table.append(entry)

        return vlan_table

    def get_arp_table(self):
        """
        Get ARP table.
        """
        arp_table = []

        arp_cmd = 'show arp'
        output = self.device.send_command(arp_cmd)
        output = output.split('\n')

        # Skip the first two lines which is the header
        output = output[2:-1]

        for line in output:
            if len(line) == 0:
                return {}
            if len(line.split()) == 6:
                address, mac, interface, macresolved, age, typ = line.split()
                try:
                    if age == '-':
                        age = 0
                    age = float(age)
                except ValueError:
                    print(
                        "Unable to convert age value to float: {}".format(age)
                        )
                entry = {
                    'interface': interface,
                    'mac': helpers.mac(mac),
                    'ip': address,
                    'type': typ,
                    'age': age
                }
                arp_table.append(entry)
            else:
                raise ValueError(
                    "Unexpected output from: {}".format(line.split()))

        return arp_table

    def get_interfaces(self):

        interface_list = {}

        iface_cmd = 'show interface'
        output = self.device.send_command(iface_cmd)
        output = output.splitlines()

        for line in output:

            fields = line.split()

    def get_interfaces(self):

        interface_list = {}

        iface_cmd = 'show ip interface brief'
        output = self.device.send_command(iface_cmd)
        output = output.split('\n')
        output = output[3:-1]

        for line in output:

            fields = line.split()

            """
            # Brocade CLI outputs
            #
            sw0# show ip interface brief
            Interface                      IP-Address      Status                    Protocol
            ==========================     ==========      ====================      ========
            GigabitEthernet 0/1             unassigned        administratively down     down
            GigabitEthernet 0/2             unassigned        administratively down     down
            GigabitEthernet 0/3             unassigned        administratively down     down
            GigabitEthernet 0/4             unassigned        administratively down     down

            Interface              IP-Address          Vrf                     Status                    Protocol
            ==================     ==========          ==================      ====================      ========
            Ethernet 0/1           unassigned          default-vrf             administratively down     down
            Ethernet 0/2           unassigned          default-vrf             administratively down     down
            Ethernet 0/3           unassigned          default-vrf             administratively down     down
            """


            # Check for administratively down
            if len(fields) == 6:
                interface_type, interface, ip_address, status, \
                    status2, protocol = fields
            elif len(fields) == 7:
                interface_type, interface, ip_address, vrf, status, \
                    status2, protocol = fields
            else:
                raise ValueError(u"Unexpected Response from the device")

            status = status.lower()
            protocol = protocol.lower()
            if 'admin' in status:
                is_enabled = False
            else:
                is_enabled = True
            is_up = bool('up' in protocol)
            interface_list[interface] = {
                'is_up': is_up,
                'is_enabled': is_enabled,
                'interface_type': interface_type,
                'ip_address': ip_address
            }
        

        return interface_list

    def reboot(self):
        """Reload the switch."""
        cmd = "reload system\ny\n"
        self.device.send_command(cmd)

    def commit_config(self):
        """Commit the candidate configuration."""
        cmd = "copy flash://_candidate.cfg running-config"
        self.device.send_command(cmd)        

    def _checkpoint_running_config(self):
        """Checkpoint running config."""
        cmd = "oscmd rm /var/config/vcs/scripts/_running.cfg"
        self.device.send_command(cmd)
        cmd = "copy running-config flash://_running.cfg"
        self.device.send_command(cmd)

    def _checkpoint_startup_config(self):
        """Checkpoint startup config if it exists."""
        cmd = "oscmd rm /var/config/vcs/scripts/_startup.cfg"
        self.device.send_command(cmd)
        cmd = "copy startup-config flash://_startup.cfg"
        self.device.send_command(cmd)

    def load_replace_candidate(self, filename, config=None):

        dst = "%s/tmp/%s" % (os.environ['HOME'], filename)
        copyfile(filename, dst)

        cmd = "oscmd rm /var/config/vcs/scripts/_candidate.cfg"
        self.device.send_command(cmd)

        cmd = "copy scp://%s:%s@%s/tmp/%s flash://_candidate.cfg" \
            % (EXPORT_USER, EXPORT_PASSWORD, EXPORT_HOST, filename)

        self.device.send_command(cmd)

    def load_merge_candidate(self, filename=None, config=None):

        dst = "%s/tmp/%s" % (os.environ['HOME'], filename)
        copyfile(filename, dst)
        cmd = "oscmd rm /var/config/vcs/scripts/_candidate.cfg"
        self.device.send_command(cmd)
        cmd = "copy scp://%s:%s@%s/tmp/%s flash://_candidate.cfg" \
            % (EXPORT_USER, EXPORT_PASSWORD, EXPORT_HOST, filename)

        self.device.send_command(cmd)

    def rollback_config(self):

        print "Reloading previous checkpoint ..."
        cmd = "copy flash://_running.cfg running_config"
        self.device.send_command(cmd) 
        self.reboot()

    def compare_config(self):

        cmd = "oscmd diff /var/config/vcs/scripts/_running.cfg /var/config/vcs/scripts/_candidate.cfg"
        self.device.send_command(cmd)

    def discard_config(self):
        cmd = "oscmd rm /var/config/vcs/scripts/_candidate.cfg"
        self.device.send_command(cmd)

    def get_interfaces_counters(self):
        cmd = "show interface stats brief"
        lines = self.device.send_command(cmd)
        lines = lines.split('\n')

        counters_table = []
        # Skip the first four lines which is the header
        lines = lines[4:-1]

        for line in lines:
            if len(line) == 0:
                return {}
            if len(line.split()) == 9:
                interface_type, interface, pkts_rx, pkts_tx, \
                    err_rx, err_tx, discards_rx, discards_tx, crc_rx = \
                    line.split()
                entry = {
                    'interface_type': interface_type,
                    'interface': interface,
                    'pkts_rx': pkts_rx,
                    'pkts_tx': pkts_tx
                }
                counters_table.append(entry)
            else:
                raise ValueError(
                    "Unexpected output from: {}".format(line.split()))

        return counters_table
            
    def get_mac_address_table(self):
        """Get mac address table (TBD)."""

        #with pynos.device.Device(conn=conn, auth=auth) as dev:
        #pprint(dev.mac_table)
        
        cmd = "show mac-address-table"
        lines = self.device.send_command(cmd)
        lines = lines.splitlines()

        mac_address_table = []
        # Skip the first 1 lines
        lines = lines[1:-1]

        for line in lines:

            if len(line) == 0:
                return mac-address-table

            if len(line.split()) == 6:
                vlan, mac, typ, state, interface_type, interface = \
                    line.split()

                if state == "Inactive":
                    active = False
                else:
                    active = True

                if typ == "Static":
                    typ = True
                else:
                    typ = False

                entry = {
                    'mac': helpers.mac(mac).decode('utf-8'),
                    'interface': interface.decode('utf-8'),
                    'vlan': int(vlan),
                    'static': typ,
                    'active': active,
                    'moves': int(-1), 
                    'last_move': float(0), 
                    }

                mac_address_table.append(entry)
            else:
                raise ValueError(
                    "Unexpected output from: {}".format(line.split()))

        return mac_address_table
            
