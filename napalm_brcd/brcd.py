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

from netmiko import ConnectHandler, FileTransfer
from napalm_base.base import NetworkDriver
from napalm_base.exceptions import ReplaceConfigException, MergeConfigException

import difflib
import os, sys
import re
from shutil import copyfile
from StringIO import StringIO
import pdb

EXPORT_HOST = "10.24.88.6"
EXPORT_USER = "shh"
EXPORT_PASSWORD = "ss"

#SWITCH_HOST = "10.24.84.38"
#EXPORT_USER = "admin"
#EXPORT_PASSWORD = "password"

CANDIDATE_CONFIG = "_candidate.cfg"

class BrcdDriver(NetworkDriver):

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):

        if optional_args is None:
            optional_args = {}

        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.port = optional_args.get('port', 22)


    def open(self):
        """Open a connection to the device."""
        self.device = ConnectHandler(device_type='brocade_vdx',
                                     ip=self.hostname,
                                     port=self.port,
                                     username=self.username,
                                     password=self.password,
                                     verbose=True)

    def close(self):
        """Close the connection to the device."""
        self.device.disconnect()

    def cli(self, commands=None):
        """
        Execute a list of commands and return the output in a dictionary format using the
        command as the key.

        """
        cli_output = dict()

        if type(commands) is not list:
            raise TypeError('Please enter a valid list of commands!')

        for command in commands:
            output = self.device.send_command(command)
            if 'Invalid input detected' in output:
                raise ValueError('Unable to execute command "{}"'.format(command))
            cli_output.setdefault(command, {})
            cli_output[command] = output

        return cli_output

    def send_command(self, cmd):
        output = self.device.send_command(cmd)
        if 'Invalid input detected' in output:
            raise ValueError('Unable to execute command "{}"'.format(cmd))
        return output

    def get_environment(self):

        environment = {}
        cpu_cmd = 'show proc cpu'

        output = self.device.send_command(cpu_cmd)
        output = output.strip()
        environment.setdefault('cpu', {})
        environment['cpu'][0] = {}
        environment['cpu'][0]['%load'] = 0.0

        lines = output.splitlines()

        while True:
            line = lines.pop(0)
            if 'Realtime Statistics' in line:
                line = lines.pop(0)
                # CPU utilization for five seconds: 2%/0%; one minute: 2%; five minutes: 1%
                cpu_regex = r'^.*One minute: (\d+\.\d+); Five.*$'
                match = re.search(cpu_regex, line)
                if match is None:
                    break
                environment['cpu'][0]['%load'] = float(match.group(1))
                break

        # Initialize 'power', 'fan', and 'temperature' to default values (not implemented)
        environment.setdefault('power', {})
        environment['power']['invalid'] = {'status': True, 'output': -1.0, 'capacity': -1.0}
        environment.setdefault('fans', {})
        environment['fans']['invalid'] = {'status': True}
        environment.setdefault('temperature', {})
        environment['temperature']['invalid'] = {'is_alert': False, 'is_critical': False, 'temperature': -1.0}
        return environment


    def get_facts(self):
        cmd = "show system"
        fact_table = {}
        output = self.device.send_command(cmd)
        output = output.split('\n')
        output = output[3:-1]

        for line in output:
            if len(line) == 0:
                return {}

            match = re.search("Up Time.*: (.*)$", line)
            if match:
                uptime = match.group(1)
                fact_table["uptime"] = uptime

            match = re.search("^.*Version.*: (.*)$", line)
            if match:
                os_version = match.group(1)
                fact_table["os_version"] = os_version

            match = re.search("^Management IP.*: (.*)$", line)
            if match:
                mgmt_ip = match.group(1)
                fact_table["management_ip"] = mgmt_ip

        return fact_table


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
                address, mac, interface, macresolved, age, type = line.split()
                try:
                    if age == '-':
                        age = 0
                    age = float(age)
                except ValueError:
                    print("Unable to convert age value to float: {}".format(age))
                entry = {
                    'interface': interface,
                    'mac': mac,
                    'ip': address,
                    'age': age
                }
                arp_table.append(entry)
            else:
                raise ValueError("Unexpected output from: {}".format(line.split()))

        return arp_table

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
                interface_type, interface, ip_address, status, status2, protocol = fields
            elif len(fields) == 7:
                interface_type, interface, ip_address, vrf, status, status2, protocol = fields
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
        cmd = "reload system\ny\n"
        output = self.device.send_command(cmd)
        pass

    def commit_config(self):
        cmd = "copy flash://_candidate.cfg running-config"
        output = self.device.send_command(cmd)        

    def _checkpoint_running_config(self):
        cmd = "oscmd rm /var/config/vcs/scripts/_running.cfg"
        output = self.device.send_command(cmd)
        cmd = "copy running-config flash://_running.cfg"
        output = self.device.send_command(cmd) 
        return output

    def _checkpoint_startup_config(self):
        cmd = "oscmd rm /var/config/vcs/scripts/_startup.cfg"
        output = self.device.send_command(cmd)
        cmd = "copy startup-config flash://_startup.cfg"
        output = self.device.send_command(cmd)
        return output

    def load_replace_candidate(self, filename, config=None):

        dst = "%s/tmp/%s" % (os.environ['HOME'], filename)
        copyfile(filename, dst)

        cmd = "oscmd rm /var/config/vcs/scripts/_candidate.cfg"
        output = self.device.send_command(cmd)

        cmd = "copy scp://%s:%s@%s/tmp/%s flash://_candidate.cfg" \
            % (EXPORT_USER, EXPORT_PASSWORD, EXPORT_HOST, filename)
        output = self.device.send_command(cmd)

    def load_merge_candidate(self, filename=None, config=None):

        dst = "%s/tmp/%s" % (os.environ['HOME'], filename)
        copyfile(filename, dst)

        cmd = "oscmd rm /var/config/vcs/scripts/_candidate.cfg"
        output = self.device.send_command(cmd)

        cmd = "copy scp://%s:%s@%s/tmp/%s flash://_candidate.cfg" \
            % (EXPORT_USER, EXPORT_PASSWORD, EXPORT_HOST, filename)

        output = self.device.send_command(cmd)

    def rollback_config(self):

        print "Reloading previous checkpoint ..."
        cmd = "copy flash://_running.cfg running_config"
        output = self.device.send_command(cmd) 
        self.reboot()
        return output

    def compare_config(self):

        cmd = "oscmd diff /var/config/vcs/scripts/_running.cfg /var/config/vcs/scripts/_candidate.cfg"
        output = self.device.send_command(cmd)
        return output

    def discard_config(self):
        cmd = "oscmd rm /var/config/vcs/scripts/_candidate.cfg"
        output = self.device.send_command(cmd)


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
                interface_type, interface, pkts_rx, pkts_tx, err_rx, err_tx, discards_rx, discards_tx, crc_rx = \
                    line.split()
                entry = {
                    'interface_type': interface_type,
                    'interface': interface,
                    'pkts_rx': pkts_rx,
                    'pkts_tx': pkts_tx
                }
                counters_table.append(entry)
            else:
                raise ValueError("Unexpected output from: {}".format(line.split()))

        return counters_table
            

    def get_mac_address_table(self):
        cmd = "show mac-address-table"
        lines = self.device.send_command(cmd)
        lines = lines.split('\n')
        mac_table = []
        return mac_table


    def get_lldp_neigbors(self):
        pass

    def get_lldp_neigbors(self, interface = ''):
        pass



