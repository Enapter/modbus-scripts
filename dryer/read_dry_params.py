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

from enum import IntEnum
from typing import Any, Final, Self

try:
    from pyModbusTCP import client, utils

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
DRYER_PT00_INPUT: Final[int] = 6010
DRYER_PT01_INPUT: Final[int] = 6012
DRYER_STATE_INPUT: Final[int] = 6021

# Error message usually indicating that DCN is disabled
SLAVE_DEVICE_FAILURE: Final[str] = 'slave device failure'


class DryerState(IntEnum):
    """
    Enum values for dryer state input register (6021).
    """
    UNKNOWN = -1

    NONE = 0
    WAITING_FOR_POWER = 257
    STOPPED_BY_USER = 259
    STARTING = 260
    STANDBY = 262
    WAITING_FOR_PRESSURE = 263
    IDLE = 265
    DRYING_0 = 513
    COOLING_0 = 514
    SWITCHING_0 = 515
    PRESSURIZING_0 = 516
    FINALIZING_0 = 517
    DRYING_1 = 769
    COOLING_1 = 770
    SWITCHING_1 = 771
    PRESSURIZING_1 = 772
    FINALIZING_1 = 773
    ERROR = 1281
    BYPASS = 1537
    BYPASS_1 = 1793
    BYPASS_2 = 2049
    MAINTENANCE = 2305
    EXPERT = 2561
    FSR_WAIT_BEGIN = 2817
    FSR_WAIT_CONFIRM = 2818
    FSR_WAIT_END = 2819
    FSR_DECLINED = 2820
    IDCN_WAIT_START = 3073
    IDCN_WAIT_CONFIRM = 3074
    IDCN_BEGIN = 3075
    IDCN_COMMIT = 3076
    IDCN_COMMIT_ACK = 3077
    IDCN_WAIT_SYNCED = 3078
    IDCN_SYNCED = 3079
    IDCN_DECLINED = 3080
    IDCN_CANCEL = 3081
    OTA_FW = 3328

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reading DRY params with Modbus'
    )

    parser.add_argument(
        '--modbus-ip', '-i', help='Modbus IP address', required=True
    )

    parser.add_argument(
        '--modbus-port', '-p', help='Modbus port', type=int, default=502
    )

    return parser.parse_args()


def _read_input_registers(
    modbus_client: client.ModbusClient, address: int, count: int
) -> list[int]:
    """
    Read input registers.
    """
    return modbus_client.read_input_registers(reg_addr=address, reg_nb=count)


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
        # Read dryer state input register, address is 6021. Register type is
        # uint16, so number of registers to read is 16 / 16 = 1.
        raw_dryer_state: list[int] = modbus_client.read_input_registers(
            reg_addr=DRYER_STATE_INPUT, reg_nb=1
        )

        print(f'Got raw dryer state data: {raw_dryer_state}')

        print(
            f'Got decoded human-readable dryer state:'
            f' {DryerState(raw_dryer_state[0]).name}'
        )

        # Read 6010 and 6012 input registers. Each register type is float32, so
        # number of registers to read is 32 / 16 = 2.
        for register, description in (
            (DRYER_PT00_INPUT, 'PT00 pressure'),
            (DRYER_PT01_INPUT, 'PT01 pressure')
        ):
            raw_pressure_data: list[int] = (
                _read_input_registers(
                    modbus_client=modbus_client, address=register, count=2
                )
            )

            # Convert raw response to single float value with pyModbusTCP
            # utils.
            converted_pressure_value: float = utils.decode_ieee(
                val_int=utils.word_list_to_long(
                    val_list=raw_pressure_data
                )[0]
            )

            print(f'Got {description} in bar: {converted_pressure_value}')

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
