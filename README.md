# Napalm Brocade Driver

This driver is vendor specific south-bound implentation of the NAPALM API. Supported here are Brocade's SLX and NOS based switches.

## Instructions

Please see instuction at:
https://napalm.readthedocs.io/en/latest/

##Caveats

Brocade switches always perform a commit at the end of each CLI. Hence there is no explict "commit" command at the CLI level. The implementation here simulates a commit operation.

When a "merge" is requested through the Napalm API (config_load_merge) the file is actually pushed to the switch, however it is not applied to the switch. It is stored on the switch as _candidate.cfg file in the switch filesystem. When a commit is requested this file is merged with the running config. Then the _candidate.cfg is deleted from the switch. A discard would have deleted this file without commiting the operations specified in the file.

The load replace is implemented similar to the merge operation.

