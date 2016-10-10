# Sample script to demonstrate loading a config for a device.
#
# Note: this script is as simple as possible: it assumes that you have
# followed the lab setup in the quickstart tutorial, and so hardcodes
# the device IP and password.  You should also have the
# 'new_good.conf' configuration saved to disk.


import shlex
import json

from oslo_config import cfg

import napalm

service_opts = [

    cfg.StrOpt('switch_type',
                  default="",
                  help='Type of Brocade switch (SLX/VDX)'),
    cfg.StrOpt('switch_ip',
                  default="",
                  help='Switch Mgmt IP Address'),
    cfg.StrOpt('switch_username',
                 default="",
                 help='Switch Mgmt creditials - username'),
    cfg.StrOpt('switch_password',
                 default="",
                 help='Switch Mgmt creditials - password'),

    cfg.StrOpt('external_host',
                  default="",
                  help='External host where merge/candidate can be imported from'),
    cfg.StrOpt('external_host_username',
                 default="",
                 help='External Host creditials'),
    cfg.StrOpt('external_host_password',
                 default="",
                 help='External Host creditials')

]

CONF = cfg.CONF
CONF.register_opts(service_opts, "napalm")


def show_help():
    """Show the help menu."""

    print "\n\n"

    print "[ifaces]    Get Interfaces"
    print "[icounters] Get Interface counters"
    print "\n"

    print "[vlans] Show vlans"
    print "[arps]   Get ARP table"
    print "[macs]   Get MAC Table"
    print "[facts] Facts about the switch"
    print "[env]   Get Enviroment"
    print "\n"

    print "[checkpoint] Checkpoint running and startup config"
    print "[merge]      Merge candidate"
    print "[replace]    Replace candidate"
    print "[discard]    Discard candidate"
    print "[rollback]   Rollback to previous checkpoint"
    print "[compare]    Compare candidate config against running-config"
    print "[commit]     Commit Candidate"
    print "\n"

    print "[reboot]  Reload the switch with startup-config (reboot)"

    print "[help|?] Help (this message)"
    print "[quit|q] Quit"
    
def main():

    # Use the appropriate network driver to connect to the device:
    driver = napalm.get_network_driver('brocade')

    # Connect and Open device:
    device = driver(hostname=CONF.napalm.switch_ip, username=CONF.napalm.switch_username,
                    password=CONF.napalm.switch_password, optional_args={'port': 22})
    device.open()

    show_help()

    while True:
        line = raw_input("\nOperation you would like to perform? (For help: [help | ?]): ").lower()
        arg = shlex.split(line)
        argc = len(arg)
        if argc < 1:
            continue

        choice = arg[0]

        if choice == 'help' or choice == "?":
            show_help()

        elif choice == 'q' or choice == "quit":
            print "\nGoodbye\n"
            break

        elif choice == 'checkpoint':
            device._checkpoint_running_config()
            device._checkpoint_startup_config()
            print "Checkpoint of startup and running config DONE"

        elif choice == 'ifaces':
            table = device.get_interfaces()
            print json.dumps(table, sort_keys=True, indent=4)

        elif choice == 'icounters':
            table = device.get_interfaces_counters()
            print json.dumps(table, sort_keys=True, indent=4)

        elif choice == 'env':
            env = device.get_environment()
            print json.dumps(env, sort_keys=True, indent=4)

        elif choice == 'vlans':
            table = device.get_vlan_table()
            print json.dumps(table, sort_keys=True, indent=4)

        elif choice == 'arps':
            table = device.get_arp_table()
            print json.dumps(table, sort_keys=True, indent=4)

        elif choice == 'macs':
            table = device.get_mac_address_table()
            print json.dumps(table, sort_keys=True, indent=4)

        elif choice == 'facts':
            table = device.get_facts()
            print json.dumps(table, sort_keys=True, indent=4)

        elif choice == 'merge':
            if argc < 2:
                print "Merge requires a file argument"
                continue
            st = device.load_merge_candidate(arg[1])
            print "Merge loaded, Commit pending"

        elif choice == 'replace':
            st = device.load_replace_candidate("candidate.cfg")
            print "Merge loaded, Commit pending"

        elif choice == 'discard':
            st = device.discard_config()

        elif choice == 'compare':
            st = device._checkpoint_running_config()
            st = device.compare_config()
            print st

        elif choice == 'rollback':
            st = device.rollback_config()
            st = device.reboot()
            break

        elif choice == 'commit':
            st = device.commit_config()
            st = device.discard_config()
            print "Committed"

        elif choice == 'reboot':
            print "Switch rebooting ...Goodbye!"
            st = device.reboot()
            break

        else:
            print "Unrecognized command!"


    device.close()

    print 'Done.'

if __name__ == '__main__':
    CONF(default_config_files=['napalm.conf'])
    main()

