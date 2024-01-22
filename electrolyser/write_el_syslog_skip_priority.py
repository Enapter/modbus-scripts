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
import random
import sys
import time

from enum import IntEnum
from typing import Any, Final, Optional, Self

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

# Timeout after writing to somehow guarantee that value is updated
REGISTER_WRITE_TIMEOUT: Final[int] = 2


class ModbusWriteException(RuntimeError):
    """
    Custom exception to indicate runtime problems writing modbus registers.
    """

    pass


class Holdings(IntEnum):
    """
    Holding registers.
    """

    CONFIGURATION_BEGIN = 4000
    CONFIGURATION_COMMIT = 4001
    LOG_SKIP_PRIORITY = 4042


class Inputs(IntEnum):
    """
    Input registers.
    """

    CONFIGURATION_IN_PROGRESS = 4000
    CONFIGURATION_OVER_MODBUS = 4001
    CONFIGURATION_LAST_RESULT = 4002
    CONFIGURATION_INVALIDATED_HOLDING = 4004


class LogSkipPriority(IntEnum):
    """
    Enum values for Log_SyslogSkipPriority holding register (4042).
    """

    UNKNOWN = -1

    DISABLE_LOGGING = 0
    FATAL_ERRORS = 1
    ALL_ERRORS = 2
    ERRORS_AND_WARNINGS = 3
    ERRORS_AND_WARNINGS_AND_IMPORTANT_MESSAGES = 4
    ERRORS_AND_WARNINGS_AND_MESSAGES_EXCEPT_DEBUG = 5
    ALL_MESSAGES = 6

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN

    @classmethod
    def values(cls, exclude_values: Optional[list[Self]] = None) -> list[Self]:
        """
        List enum values without UNKNOWN with possibility to exclude specific
        values.
        """
        values_: list[LogSkipPriority] = list(cls)

        values_.remove(cls.UNKNOWN)

        if exclude_values is not None:
            for value in exclude_values:
                if value is not cls.UNKNOWN:
                    values_.remove(value)

        return values_


class ConfigurationLastResult(IntEnum):
    """
    Enum values for Configuration-LastResult input register (4002).
    """

    UNKNOWN = -1

    OK = 0
    PERMANENT = 1
    NO_ENTRY = 2
    I_O = 5
    TRY_AGAIN = 11
    ACCESS_DENIED = 13
    BUSY = 16
    INVALID = 22

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def _write_single_register(
    modbus_client: client.ModbusClient, address: int, value: int
) -> None:
    """
    Write 16 bits register.
    """
    modbus_client.write_single_register(reg_addr=address, reg_value=value)

    time.sleep(REGISTER_WRITE_TIMEOUT)


def _write_multiple_registers(
    modbus_client: client.ModbusClient, address: int, values: list[int]
) -> None:
    """
    Write over 16 bits register.
    """
    modbus_client.write_multiple_registers(
        regs_addr=address, regs_value=values
    )

    time.sleep(REGISTER_WRITE_TIMEOUT)


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


def _read_syslog_skip_priority(
    modbus_client: client.ModbusClient
) -> LogSkipPriority:
    """
    Read system logs priority holding register, address is 4042. Register type
    is int32, so number of registers to read is 32 / 16 = 2. Convert raw
    response to single int value with pyModbusTCP utils.
    """
    return LogSkipPriority(
        utils.get_list_2comp(
            val_list=utils.word_list_to_long(
                val_list=_read_holding_registers(
                    modbus_client=modbus_client,
                    address=Holdings.LOG_SKIP_PRIORITY.value, count=2
                )
            ), val_size=32
        )[0]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Writing EL syslog skip priority with Modbus'
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
        initial_syslog_skip_priority: LogSkipPriority = (
            _read_syslog_skip_priority(modbus_client=modbus_client)
        )

        print(
            f'Got initial system logs priority: '
            f'{initial_syslog_skip_priority.name}'
        )

        # 4xxx holding registers are configuration registers. First we must
        # check if another configuration is in progress. Reading
        # Configuration-InProgress input register, address is 4000. Register
        # type is boolean, technically it's similar to uint16, so number of
        # registers to read is 16 / 16 = 1.
        if bool(
            _read_input_registers(
                modbus_client=modbus_client,
                address=Inputs.CONFIGURATION_IN_PROGRESS.value, count=1
            )[0]
        ):
            raise ModbusWriteException(
                'Seems like another configuration is in progress'
            )

        try:
            print('Begin configuration...')

            # Write Configuration-Begin holding register, address is 4000.
            # Register type is boolean, technically it's similar to uint16.
            _write_single_register(
                modbus_client=modbus_client,
                address=Holdings.CONFIGURATION_BEGIN.value, value=1
            )

            print('Check configuration source...')

            # Read Configuration-OverModbus input register, address is 4001.
            # Register type is boolean, technically it's similar to uint16,
            # so number of registers to read is 16 / 16 = 1.
            if not bool(
                _read_input_registers(
                    modbus_client=modbus_client,
                    address=Inputs.CONFIGURATION_OVER_MODBUS.value, count=1
                )[0]
            ):
                raise ModbusWriteException(
                    'Seems like configuration source is not Modbus'
                )

            new_syslog_skip_priority: LogSkipPriority = random.choice(
                LogSkipPriority.values(
                    exclude_values=[initial_syslog_skip_priority]
                )
            )

            print(f'Write new priority ({new_syslog_skip_priority.name})...')

            # Write system logs priority holding register, address is 4042.
            # Register type is int32, so technically we can write any supported
            # value. Values less than 0 are considered as DISABLE_LOGGING,
            # values great than 6 are considered as ALL_MESSAGES. Convert
            # generated value with pyModbusTCP utils.
            _write_multiple_registers(
                modbus_client=modbus_client,
                address=Holdings.LOG_SKIP_PRIORITY.value,
                values=utils.long_list_to_word(
                    val_list=[
                        utils.get_2comp(
                            val_int=new_syslog_skip_priority.value, val_size=32
                        )
                    ]
                )
            )

            print('Check configuration last result...')

            # Read Configuration-LastResult input register, address is 4002.
            # Register type is int32, so number of registers to read is
            # 32 / 16 = 2. Convert raw response to single int value with
            # pyModbusTCP utils.
            configuration_last_result: ConfigurationLastResult = (
                ConfigurationLastResult(
                    utils.get_list_2comp(
                        val_list=utils.word_list_to_long(
                            val_list=_read_input_registers(
                                modbus_client=modbus_client,
                                address=Inputs.CONFIGURATION_LAST_RESULT.value,
                                count=2
                            )
                        ), val_size=32
                    )[0]
                )
            )

            if configuration_last_result != ConfigurationLastResult.OK:
                # Read Configuration-InvalidatedHolding input register, address
                # is 4004. Register type is uint32, so number of registers to
                # read is 16 / 16 = 1.
                configuration_invalidated_holding: int = (
                    _read_input_registers(
                        modbus_client=modbus_client,
                        address=Inputs.CONFIGURATION_INVALIDATED_HOLDING.value,
                        count=1
                    )[0]
                )

                raise ModbusWriteException(
                    f'Configuration last result is'
                    f'{configuration_last_result.name}. Possible problematic'
                    f'register is {configuration_invalidated_holding}'
                )

            print('Commit configuration...')

            # Write Configuration-Commit holding register, address is 4001.
            # Register type is boolean, technically it's similar to uint16.
            # We must write 1 to commit configuration.
            _write_single_register(
                modbus_client=modbus_client,
                address=Holdings.CONFIGURATION_COMMIT.value, value=1
            )

        except ModbusWriteException:
            print('Rollback configuration...')

            # Write Configuration-Commit holding register, address is 4001.
            # Register type is boolean, technically it's similar to uint16.
            # We must write 0 to rollback configuration.
            _write_single_register(
                modbus_client=modbus_client,
                address=Holdings.CONFIGURATION_COMMIT.value, value=0
            )

            raise

        updated_syslog_skip_priority: LogSkipPriority = (
            _read_syslog_skip_priority(modbus_client=modbus_client)
        )

        print(
            f'Got updated system logs priority: '
            f'{updated_syslog_skip_priority.name}'
        )

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
