# Copyright 2024 Enapter
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import sys
import time

from typing import Final

try:
    from pyModbusTCP import client

except ImportError:
    print(
        'No pyModbusTCP module installed.\n.'
        '1. Create virtual environment\n'
        '2. Run \'pip install pyModbusTCP==0.2.1\''
    )

    raise


# Supported Python version
MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 10)

# Registers addresses
DRYER_REBOOT_HOLDING: Final[int] = 6020
DRYER_SAVE_CONFIG_HOLDING: Final[int] = 6022

# Timeout (seconds) after writing to somehow guarantee that value is updated
REGISTER_WRITE_TIMEOUT: Final[int] = 2

# Timeout (seconds) to complete dryer reboot
REBOOT_TIMEOUT: Final[int] = 5

# Error message usually indicating that DCN is disabled
SLAVE_DEVICE_FAILURE: Final[str] = 'slave device failure'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Write DRY reboot with Modbus'
    )

    parser.add_argument(
        '--modbus-ip', '-i', help='Modbus IP address', required=True
    )

    parser.add_argument(
        '--modbus-port', '-p', help='Modbus port', type=int, default=502
    )

    return parser.parse_args()


def _write_single_register(
    modbus_client: client.ModbusClient, address: int, value: int
) -> None:
    """
    Write 16 bits register.
    """
    modbus_client.write_single_register(reg_addr=address, reg_value=value)

    time.sleep(REGISTER_WRITE_TIMEOUT)


def _read_reboot_register(modbus_client: client.ModbusClient) -> int:
    """
    Read dryer reboot holding register, address is 6020. Register type is
    uint16, so number of registers to read is 16 / 16 = 1. Register returns
    reboot counter while reading.
    """
    return modbus_client.read_holding_registers(
        reg_addr=DRYER_REBOOT_HOLDING, reg_nb=1
    )[0]


def main() -> None:
    if sys.version_info < MIN_PYTHON_VERSION:
        raise RuntimeError(
            f'Python version >='
            f' {".".join(str(version) for version in MIN_PYTHON_VERSION)} is'
            f' required'
        )

    args: argparse.Namespace = parse_args()

    modbus_client: client.ModbusClient = client.ModbusClient(
        host=args.modbus_ip, port=args.modbus_port
    )

    try:
        print(
            f'Got initial reboot counter: '
            f'{_read_reboot_register(modbus_client=modbus_client)}'
        )

        print('Rebooting...')

        # Write reboot holding register, address is 6020. Register type is
        # uint16.
        _write_single_register(
            modbus_client=modbus_client, address=DRYER_REBOOT_HOLDING, value=1
        )

        # Write save config holding register, address is 6022. Register type is
        # uint16.
        _write_single_register(
            modbus_client=modbus_client, address=DRYER_SAVE_CONFIG_HOLDING,
            value=1
        )

        time.sleep(REBOOT_TIMEOUT)

        print(
            f'Got updated reboot counter: '
            f'{_read_reboot_register(modbus_client=modbus_client)}'
        )

    except Exception as e:
        # If something went wrong, we can access Modbus error/exception info.
        # For example, in case of connection problems, reading register will
        # return None and script will fail with error while data converting,
        # but real problem description will be stored in client.
        print(f'Exception occurred: {e}')
        print(f'Modbus error: {modbus_client.last_error_as_txt}')
        print(f'Modbus exception: {modbus_client.last_except_as_txt}')

        if SLAVE_DEVICE_FAILURE in modbus_client.last_except_as_txt:
            print('Please check that DCN is enabled')

        raise


if __name__ == '__main__':
    main()
