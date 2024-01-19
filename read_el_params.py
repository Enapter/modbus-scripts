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


class Holdings(IntEnum):
    """
    Holding registers.
    """

    PRODUCTION_RATE = 1002


class Inputs(IntEnum):
    """
    Input registers.
    """

    SYSTEM_STATE = 18
    UPTIME = 22
    TOTAL_H2_PRODUCTION = 1006
    LSH102B_IN = 7000
    LSHH102A_IN = 7001
    LSL102D_IN = 7002
    LSM102C_IN = 7003
    PSH102_IN = 7004
    TSH108_IN = 7007
    WPS104_IN = 7009


class SystemState(IntEnum):
    """
    Values for state input register (18).
    """

    UNKNOWN = -1

    INTERNAL_ERROR_SYSTEM_NOT_INITIALIZED_YET = 0
    SYSTEM_IN_OPERATION = 1
    ERROR = 2
    SYSTEM_IN_MAINTENANCE_MODE = 3
    FATAL_ERROR = 4
    SYSTEM_IN_EXPERT_MODE = 5

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def _read_input_registers(
    modbus_client: client.ModbusClient, address: int, count: int
) -> list[int]:
    """
    Read input registers.
    """
    return modbus_client.read_input_registers(reg_addr=address, reg_nb=count)


def _read_holding_registers(
    modbus_client: client.ModbusClient, address: int, count: int
) -> list[int]:
    """
    Read holding registers.
    """
    return modbus_client.read_holding_registers(reg_addr=address, reg_nb=count)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reading current EL params with Modbus'
    )

    parser.add_argument(
        '--modbus-ip', '-i', help='Modbus IP address', required=True
    )

    parser.add_argument(
        '--modbus-port', '-p', help='Modbus port', type=int, default=502
    )

    return parser.parse_args()


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
        # Read and decode system state input register, address is 18. Register
        # type is enum16, technically it's similar to uint16, so number of
        # registers to read is 16 / 16 = 1.
        system_state: SystemState = SystemState(
            _read_input_registers(
                modbus_client=modbus_client,
                address=Inputs.SYSTEM_STATE.value, count=1
            )[0]
        )

        print(f'Got system state: {system_state.name}')

        # Read uptime input register, address is 22. Register type is uint32,
        # so number of registers to read is 32 / 16 = 2.
        raw_uptime_data: list[int] = _read_input_registers(
            modbus_client=modbus_client, address=Inputs.UPTIME.value, count=2
        )

        # Convert raw response to single int value with pyModbusTCP utils.
        converted_uptime: int = utils.word_list_to_long(
            val_list=raw_uptime_data
        )[0]

        print(
            f'Got uptime in seconds: {converted_uptime}'
        )

        # Read stack total H2 production input register, address is 1006.
        # Register type is float32, so number of registers to read is
        # 32 / 16 = 2.
        raw_h2_production_data: list[int] = _read_input_registers(
            modbus_client=modbus_client,
            address=Inputs.TOTAL_H2_PRODUCTION.value, count=2
        )

        # Convert raw response to single float value with pyModbusTCP utils.
        converted_h2_production: float = utils.decode_ieee(
            val_int=utils.word_list_to_long(val_list=raw_h2_production_data)[0]
        )

        print(f'Got total H2 production in NL: {converted_h2_production}')

        # Read production rate holding register, address is 1002. Register type
        # is float32, so number of registers to read is 32 / 16 = 2.
        raw_production_rate_data: list[int] = (
            _read_holding_registers(
                modbus_client=modbus_client,
                address=Holdings.PRODUCTION_RATE.value, count=2
            )
        )

        # Convert raw response to single float value with pyModbusTCP utils.
        converted_production_rate: float = utils.decode_ieee(
            val_int=utils.word_list_to_long(
                val_list=raw_production_rate_data
            )[0]
        )

        print(f'Got production rate in %: {converted_production_rate}')

        # Read 7000, 7001, 7002, 7003, 7004, 7007 and 7009 input registers
        # (switches). Each register type is boolean, technically it's similar
        # to uint16, so number of registers to read is 16 / 16 = 1.
        for register, description in (
            (Inputs.LSH102B_IN, 'High Electrolyte Level Switch'),
            (Inputs.LSHH102A_IN, 'Very High Electrolyte Level Switch'),
            (Inputs.LSL102D_IN, 'Low Electrolyte Level Switch'),
            (Inputs.LSM102C_IN, 'Medium Electrolyte Level Switch'),
            (Inputs.PSH102_IN, 'Electrolyte Tank High Pressure Switch'),
            (
                Inputs.TSH108_IN,
                'Electronic Compartment High Temperature Switch'
            ),
            (Inputs.WPS104_IN, 'Chassis Water Presence Switch')

        ):
            switch_value: bool = bool(
                _read_input_registers(
                    modbus_client=modbus_client, address=register.value, count=1
                )[0]
            )

            print(f'{register.name} ({description}) is {switch_value}')

    except Exception as e:
        # If something went wrong, we can access Modbus error/exception info.
        # For example, in case of connection problems, reading register will
        # return None and script will fail with error while data converting,
        # but real problem description will be stored in client.
        print(f'Exception occurred: {e}')
        print(f'Modbus error: {modbus_client.last_error_as_txt}')
        print(f'Modbus exception: {modbus_client.last_except_as_txt}')

        raise


if __name__ == '__main__':
    main()
