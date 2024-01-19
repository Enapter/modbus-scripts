## Introduction

This repository contains examples of interaction with Enapter devices over
Modbus communication protocol. Writing holding registers allows to execute 
commands (e.g. reboot), set specific parameters or update configuration.

Reading registers (both holding and inputs) allows to get current hardware status 
(e.g. switches states, H2 production parameters, timings, etc.), current configuration,
detect configuration problems.

All information regarding registers, events (errors/warnings), etc. is available at [Enapter Handbook](https://handbook.enapter.com).

### Requirements

Python is used as programming language, version >= 3.10 is required.
Please refer to the actual [downloads](https://www.python.org/downloads/) and [documentation](https://www.python.org/doc/).

Git is required to clone the repository.
Please refer to the actual [downloads](https://www.git-scm.com/downloads) and [documentation](https://www.git-scm.com/doc).

[pyModbusTCP](https://pypi.org/project/pyModbusTCP/0.2.1/) package is required.
Please refer to the actual documentation regarding [usage of virtual environments](https://docs.python.org/3/library/venv.html) and [packages installation](https://packaging.python.org/en/latest/tutorials/installing-packages/).

### Running scripts

Please refer to the actual [documentation](https://docs.python.org/3/using/cmdline.html) regarding general information about running Python scripts.

Each script requires two parameters - Modbus IP address and Modbus port.
IP address is required parameter, default port is _502_.

**Running script with default port:**
```
python3 <path_to_script>/<script_name>.py --modbus-ip <address> 
```

**Running script with custom port:**
```
python3 <path_to_script>/<script_name>.py --modbus-ip <address> --modbus-port <port>
```

### Scripts description

**_read_el_control_board_serial.py_**

Read and decode control board serial number input (6) to a human-readable string value (e.g. '9E25E695-A66A-61DD-6570-50DB4E73652D').

**_read_el_device_model.py_**

Read and decode device model input register (0) to a human-readable string value (e.g. 'EL21', 'EL40', etc.).

**_read_el_errors.py_**

Read and decode errors input register (832) to a list of human-readable strings with error name and hex 
value (e.g. 'WR_20 (0x3194)'). Since new firmwares may add new events, UNKNOWN errors may be identified by hex value.

**_read_el_params.py_**

Read and decode current hardware parameters:
- system state (input, 18)
- uptime (input, 22)
- total H2 production (input, 1006)
- production rate (holding, 1002)
- high electrolyte level switch (input, 7000)
- very high electrolyte level switch (input, 7001)
- low electrolyte level switch (input, 7002)
- medium electrolyte level switch (input, 7003)
- electrolyte tank high pressure switch (input, 7004)
- electronic compartment high temperature Switch (input, 7007)
- chassis water presence switch (input, 7009)).

**_run_el_maintenance.py_**

Interactive script to perform maintenance on EL2.1/4.x by following the instructions in console.

**ATTENTION!** Maintenance requires manual actions with electrolyser such as electrolyte draining,
flushing (for 4.x) and refilling.

If script is terminated for some reason (e.g. due to network failure), in most cases it can be re-run and
maintenance will continue.

Only refilling is performed in case of first maintenance (from factory state). 

**_write_el_production_rate.py_**

- Read current value of the production rate percent holding register (1002)
- Write random value in 90-99 range
- Read register again to check that it contains new value

- write_el_reboot.py

- Write 1 to reboot holding register (4)
- Wait until electrolyser is rebooted
- Read state input register (1200)

**_write_el_syslog_skip_priority.py_**

- Read current value of the log skip priority holding register (4042)
- Check that there is no other configuration in progress (read configuration in progress input register (4000))
- Begin configuration (write 1 to the configuration begin holding register (4000))
- Ensure that configuration source is Modbus (read configuration over modbus input register (4001))
- Write random value in 0-6 range (excluding current value) to the log skip priority holding register (4042)
- Check that configuration is OK (read configuration last result input register (4002))
- Read log skip priority holding register (4042) again to check that it contains new value

NOTICE. Log skip priority holding register (4042) has int32 type, so it may contain any value in the appropriate
range. Values less than 0 are considered as DISABLE_LOGGING (0), values greater than 6 are considered as ALL_MESSAGES (6). 
