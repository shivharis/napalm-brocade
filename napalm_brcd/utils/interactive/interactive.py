# Sample script to demonstrate loading a config for a device.
#
# Note: this script is as simple as possible: it assumes that you have
# followed the lab setup in the quickstart tutorial, and so hardcodes
# the device IP and password.  You should also have the
# 'new_good.conf' configuration saved to disk.


import napalm
import sys

import os
import re
import shlex
import pdb
import pprint
import json

SWITCH_IP   = "10.24.91.128"
SWITCH_USER = "admin"
SWITCH_PASS = "password"

def show_help():

    print "\n\n"

    print "[ifaces]    Get Interfaces"
    print "[icounters] Get Interface counters"
    print "\n"

    print "[arp]   Get ARP table"
    print "[mac]   Get MAC Table"
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
    
def main(config_file):
    """Load a config for the device."""

    if not (os.path.exists(config_file) and os.path.isfile(config_file)):
        msg = 'Missing or invalid config file {0}'.format(config_file)
        raise ValueError(msg)

    print 'Loading config file {0}.'.format(config_file)


    # Use the appropriate network driver to connect to the device:
    driver = napalm.get_network_driver('brcd')

    # Connect and Open device:
    device = driver(hostname=SWITCH_IP, username=SWITCH_USER,
                    password=SWITCH_PASS, optional_args={'port': 22})
    device.open()

    pp = pprint.PrettyPrinter(indent=4)
    show_help()

    while True:
        line = raw_input("\nOperation you would like to perform? (For help: [help | ?]): ")
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
            st = device._checkpoint_running_config()
            st = device._checkpoint_startup_config()
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
    if len(sys.argv) < 2:
        print 'Please supply the full path to "new_good.conf"'
        sys.exit(1)
    config_file = sys.argv[1]

    main(config_file)

