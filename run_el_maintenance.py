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
import os
import sys
import time

from enum import IntEnum, StrEnum
from typing import Any, Final, Self, TypeAlias, Union

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

# Windows platform id
WIN32: Final[str] = 'win32'

# Timeout (seconds) to complete draining
DRAINING_TIMEOUT: Final[int] = 300 * 2

# Timeout (seconds) to complete refilling
REFILLING_TIMEOUT: Final[int] = 300

# Timeout (seconds) to check refilling state
REFILLING_STATE_CHECK_TIMEOUT: Final[int] = 5

# Timeout (seconds) to check electrolyte presence while draining/refilling
ELECTROLYTE_PRESENCE_CHECK_TIMEOUT: Final[int] = 10

# Timeout (seconds) after writing to somehow guarantee that value is updated
REGISTER_WRITE_TIMEOUT: Final[int] = 2

# Check pressure and electrolyte presence (optionally) after pipe connection
MAX_WATER_PIPE_CONNECT_ATTEMPTS: Final[int] = 5

INPUT_CONFIRMATION: Final[str] = 'YES'


class MaintenanceModeException(RuntimeError):
    """
    Custom exception to indicate runtime problems during Maintenance.
    """

    pass


class WaterPipeException(RuntimeError):
    """
    Custom exception to indicate problems with water pipe.
    """

    pass


class HighElectrolyteLevelException(RuntimeError):
    """
    Custom exception to indicate unexpected high electrolyte level.
    """

    pass


class ElectrolyteLevel(IntEnum):
    """
    Representation of electrolyte levels for convenience.
    """

    EMPTY = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


class ConsoleColor(StrEnum):
    """
    Console colors including the end tag.
    """

    CYAN = '\033[96m'
    GREEN = '\033[32m'
    RED = '\033[91m'
    YELLOW = '\033[33m'

    # Special tag to end colored text.
    END = '\033[0m'


class Holdings(IntEnum):
    """
    Holding registers.
    """

    MAINTENANCE = 1013
    FLUSHING = 1015
    REFILLING_MINWATERPPESSURE_BAR = 4400
    REFILLING_MAXWATERPPESSURE_BAR = 4402
    REFILLING_MIXINGTIME_MS = 4418


class Inputs(IntEnum):
    """
    Input registers.
    """

    DEVICE_MODEL = 0
    WARNINGS = 768
    ERRORS = 832
    STATE = 1200
    REFILLING_STATE = 1201
    LSH102B_IN = 7000  # High Electrolyte Level
    LSHH102A_IN = 7001  # Very High Electrolyte Level
    LSL102D_IN = 7002  # Low Electrolyte Level
    LSM102C_IN = 7003  # Medium Electrolyte Level
    PT105_IN_BAR = 7516  # Water Inlet Pressure


class DeviceModel(StrEnum):
    """
    Values for ProjectId input register (0).
    """

    UNKNOWN = 'UNKNOWN'

    # Specific value for EL21.
    EL21 = 'EL21'

    # Specific values for EL40.
    EL40 = 'EL40'
    ES40 = 'ES40'

    # Specific value for EL41.
    ES41 = 'ES41'

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


class State(IntEnum):
    """
    Enum values for Electrolyser state input register (1200).
    """

    UNKNOWN = -1

    # Common states for EL2.1 and EL4.x.
    HALTED = 0
    MAINTENANCE_MODE = 1
    IDLE = 2
    STEADY = 3
    STAND_BY = 4
    CURVE = 5
    BLOWDOWN = 6

    # Specific state for EL40.
    RECOMBINER = 7

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


class RefillingState(IntEnum):
    """
    Enum values for Electrolyser refilling state input register (1201).
    """

    UNKNOWN = -1

    NONE = 0
    HALT = 1
    IDLE = 2
    FILLING = 3
    DRAINING = 4
    MAINTENANCE = 5
    KOH_REFILLING = 6
    MAINTENANCE_REFILLING = 7
    KOH_REFILLING_FINISH = 8
    FINAL_REFILLING = 9
    DEMAND_REFILLING = 10
    WAIT_FLUSHING = 11
    FLUSHING = 12
    SERVICE_REFILLING = 13

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


class ElError(IntEnum):
    """
    Values for errors register (832). Names may be used for human-readable
    description.
    """

    UNKNOWN = -1

    # Common errors for EL2.1 and EL4.x.

    INTERNAL_ERROR = 0x0FFF
    FP_01 = 0x1F81
    FP_02 = 0x1F82
    FP_03 = 0x1F83
    FP_06 = 0x1F86
    FC_10 = 0x108A
    FD_20 = 0x1114
    FR_10 = 0x118A
    FR_20 = 0x1194
    FR_50 = 0x11B2
    FR_51 = 0x11B3
    FR_52 = 0x11B4
    FR_40 = 0x11A8
    FS_01 = 0x1201
    FS_10 = 0x120A
    FT_10 = 0x128A
    ET_10 = 0x228A
    EU_10 = 0x230A
    FX_03 = 0x1403
    FX_04 = 0x1404
    FX_07 = 0x1407
    FX_11 = 0x140B
    FX_12 = 0x140C
    FX_30 = 0x141E
    FX_31 = 0x141F
    FX_33 = 0x1421
    FX_35 = 0x1423
    FX_36 = 0x1424
    FX_37 = 0x1425
    FX_38 = 0x1426
    FX_39 = 0x1427
    FF_10 = 0x148A
    FL_01 = 0x1501
    FO_30 = 0x159E

    # Specific values for EL21.
    EX_01 = 0x2401
    FX_02 = 0x1402
    FX_05 = 0x1405
    FX_08 = 0x1408
    FX_09 = 0x1409
    FX_10 = 0x140A
    FX_32 = 0x1420
    FX_34 = 0x1422
    FX_40 = 0x1428

    # Specific values for EL4.x.
    FX_13 = 0x140D
    FX_42 = 0x142A
    FB_10 = 0x170A
    FB_11 = 0x170B
    FB_20 = 0x1714
    FB_21 = 0x1715
    FY_10 = 0x178A
    FY_20 = 0x1794
    FY_21 = 0x1795
    FY_22 = 0x1796
    FY_23 = 0x1797
    FY_24 = 0x1798
    FY_25 = 0x1799
    FY_26 = 0x179A
    FY_27 = 0x179B
    FY_28 = 0x179C
    FY_29 = 0x179D
    FY_30 = 0x179E
    FY_31 = 0x179F
    FY_33 = 0x1721
    FY_51 = 0x17B3
    FY_52 = 0x17B4
    FY_53 = 0x17B5
    FY_54 = 0x17B6
    FY_55 = 0x17B7
    FY_56 = 0x17B8

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


class ElWarning(IntEnum):
    """
    Values for warnings input register (768). Names may be used for
    human-readable description.
    """

    UNKNOWN = -1

    # Common warnings for EL2.1 and EL4.x.
    WP_04 = 0x3F84
    WP_05 = 0x3F85
    WR_10 = 0x318A
    WR_20 = 0x3194
    WR_21 = 0x3195
    WR_22 = 0x3196
    WR_51 = 0x31B3
    WR_52 = 0x31B4
    WR_53 = 0x31B5
    WS_21 = 0x3215
    WS_22 = 0x3216
    WS_30 = 0x321E
    WT_20 = 0x3294
    WU_10 = 0x330A
    WX_52 = 0x3434
    WX_53 = 0x3435
    WX_55 = 0x3437
    WX_59 = 0x343B
    WX_60 = 0x343C
    WX_61 = 0x343D
    WX_62 = 0x343E
    WX_63 = 0x343F
    WX_64 = 0x3440
    WX_65 = 0x3441
    WX_66 = 0x3442
    WX_67 = 0x3443
    WX_69 = 0x3445
    WL_10 = 0x350A
    WO_10 = 0x358A
    WO_20 = 0x3594
    WH_10 = 0x360A
    WH_11 = 0x360B
    WH_12 = 0x360C
    WZ_10 = 0x368A

    # Specific values for EL2.1.
    WT_21 = 0x3295
    WX_50 = 0x3432
    WX_51 = 0x3433
    WX_54 = 0x3436
    WX_56 = 0x3438
    WX_57 = 0x3439

    # Specific values for EL4.x.
    WR_23 = 0x3197
    WR_54 = 0x31B6
    WX_14 = 0x340E
    WX_15 = 0x340F
    WX_70 = 0x3446

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


Event: TypeAlias = Union[type(ElError), type(ElWarning)]


def _text_color(text: str, color: ConsoleColor) -> str:
    """
    Add color tags to string.
    """
    return f'{color}{text}{ConsoleColor.END.value}'


def _print_cyan(text: str) -> None:
    """
    Print console text with cyan color.
    """
    print(_text_color(text=text, color=ConsoleColor.CYAN))


def _print_green(text: str) -> None:
    """
    Print console text with green color.
    """
    print(_text_color(text=text, color=ConsoleColor.GREEN))


def _print_red(text: str) -> None:
    """
    Print console text with red color.
    """
    print(_text_color(text=text, color=ConsoleColor.RED))


def _print_yellow(text: str) -> None:
    """
    Print console text with yellow color.
    """
    print(_text_color(text=text, color=ConsoleColor.YELLOW))


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


def _write_single_register(
    modbus_client: client.ModbusClient, address: int, value: int
) -> None:
    """
    Write 16 bits register.
    """
    modbus_client.write_single_register(reg_addr=address, reg_value=value)

    time.sleep(REGISTER_WRITE_TIMEOUT)


def _format_event(name: str, value: int) -> str:
    """
    Format event as string representation and hex value.
    """
    return f'{name} ({hex(value)})'


def _format_warning(warning: ElWarning) -> str:
    """
    Format warning event.
    """
    return _format_event(name=warning.name, value=warning.value)


def _decode_events(
    modbus_client: client.ModbusClient, register: Inputs, event_type: Event
) -> list[str]:
    # Read and decode input register with events (warnings or errors) array.
    # These registers have specific structure - first uint16 contains total
    # amount of events. Number of registers to read is 528 / 16 = 33.
    events: list[str] = []

    raw_events_data: list[int] = modbus_client.read_input_registers(
        reg_addr=register.value, reg_nb=33
    )

    if events_count := raw_events_data[0]:
        # Total amount of events is not 0.
        events = [
            _format_event(name=event_type(event).name, value=event)
            for event in raw_events_data[1:events_count + 1]
        ]

    return events


def _decode_warnings(modbus_client: client.ModbusClient) -> list[str]:
    """
    Read and decode input register with warnings, address is 768.
    """
    return _decode_events(
        modbus_client=modbus_client, register=Inputs.WARNINGS,
        event_type=ElWarning
    )


def _decode_errors(modbus_client: client.ModbusClient) -> list[str]:
    """
    Read and decode input register with errors, address is 832.
    """
    return _decode_events(
        modbus_client=modbus_client, register=Inputs.ERRORS,
        event_type=ElError
    )


def _check_refilling_warnings(modbus_client: client.ModbusClient) -> None:
    """
    Check electrolyser refilling warnings.
    """
    print('Checking if any refilling warnings exist...')

    if active_warnings := _decode_warnings(modbus_client=modbus_client):
        if any(
            warning in (
                _format_warning(warning=ElWarning.WR_10),
                _format_warning(warning=ElWarning.WR_20),
                _format_warning(warning=ElWarning.WR_21),
                _format_warning(warning=ElWarning.WR_22),
            )
            for warning in active_warnings
        ):
            raise MaintenanceModeException(
                f'Seems like something went wrong while refilling, active'
                f' warnings are: {", ".join(active_warnings)}\nPlease'
                ' contact Enapter customer support'
            )

        else:
            _print_yellow(
                text=(
                    f'Seems like there are no refilling issues, but other'
                    f' active warnings found: {", ".join(active_warnings)}'
                )
            )

    else:
        print('No warnings found')


def _actual_state(modbus_client: client.ModbusClient) -> State:
    """
    Read and decode state input register, address is 1200. Register type is
    enum16, technically it's similar to uint16, so number of registers to read
    is 16 / 16 = 1.
    """
    state: State = State(
        _read_input_registers(
            modbus_client=modbus_client, address=Inputs.STATE.value, count=1
        )[0]
    )

    _print_cyan(text=f'{state.name} system state detected...')

    return state


def _actual_water_inlet_pressure(modbus_client: client.ModbusClient) -> float:
    """
    Read and decode water inlet pressure input register, address is 7516.
    Register type is float32, so number of registers to read is 32 / 16 = 2.
    """
    return utils.decode_ieee(
        val_int=utils.word_list_to_long(
            val_list=_read_input_registers(
                modbus_client=modbus_client, address=Inputs.PT105_IN_BAR.value,
                count=2
            )
        )[0]
    )


def _actual_refilling_state(
    modbus_client: client.ModbusClient
) -> RefillingState:
    """
    Read and decode refilling state input register, address is 1201. Register
    type is enum16, technically it's similar to uint16, so number of registers
    to read is 16 / 16 = 1.
    """
    return RefillingState(
        _read_input_registers(
            modbus_client=modbus_client, address=Inputs.REFILLING_STATE.value,
            count=1
        )[0]
    )


def _actual_refilling_mixing_time(modbus_client: client.ModbusClient) -> int:
    """
    Read and decode refilling mixing time holding register, address is 4418.
    Register type is uint32, so number of registers to read is 32 / 16 = 2.
    Decoded value is in ms, return value is in seconds.
    """
    return utils.word_list_to_long(
        val_list=_read_holding_registers(
            modbus_client=modbus_client,
            address=Holdings.REFILLING_MIXINGTIME_MS.value, count=2
        )
    )[0] // 1000


def _actual_refilling_min_water_pressure(
    modbus_client: client.ModbusClient
) -> float:
    """
    Read and decode refilling min water pressure holding register, address is
    4400. Register type is float32, so number of registers to read is
    32 / 16 = 2.
    """
    return utils.decode_ieee(
        val_int=utils.word_list_to_long(
            val_list=_read_holding_registers(
                modbus_client=modbus_client,
                address=Holdings.REFILLING_MINWATERPPESSURE_BAR.value, count=2
            )
        )[0]
    )


def _actual_refilling_max_water_pressure(
    modbus_client: client.ModbusClient
) -> float:
    """
    Read and decode refilling max water pressure holding register, address is
    4402. Register type is float32, so number of registers to read is
    32 / 16 = 2.
    """
    return utils.decode_ieee(
        val_int=utils.word_list_to_long(
            val_list=_read_holding_registers(
                modbus_client=modbus_client,
                address=Holdings.REFILLING_MAXWATERPPESSURE_BAR.value, count=2
            )
        )[0]
    )


def _low_level_switch(modbus_client: client.ModbusClient) -> bool:
    """
    Read electrolyte low level switch (7002). Register type is boolean,
    technically it's similar to uint16, so number of registers to read is
    16 / 16 = 1.
    """
    return bool(
        _read_input_registers(
            modbus_client=modbus_client, address=Inputs.LSL102D_IN.value,
            count=1
        )[0]
    )


def _medium_level_switch(modbus_client: client.ModbusClient) -> bool:
    """
    Read electrolyte medium level switch (7003). Register type is boolean,
    technically it's similar to uint16, so number of registers to read is
    16 / 16 = 1.
    """
    return bool(
        _read_input_registers(
            modbus_client=modbus_client, address=Inputs.LSM102C_IN.value,
            count=1
        )[0]
    )


def _high_level_switch(modbus_client: client.ModbusClient) -> bool:
    """
    Read electrolyte high level switch (7000). Register type is boolean,
    technically it's similar to uint16, so number of registers to read is
    16 / 16 = 1.
    """
    return bool(
        _read_input_registers(
            modbus_client=modbus_client, address=Inputs.LSH102B_IN.value,
            count=1
        )[0]
    )


def _very_high_level_switch(modbus_client: client.ModbusClient) -> bool:
    """
    Read electrolyte very high level switch (7001). Register type is boolean,
    technically it's similar to uint16, so number of registers to read is
    16 / 16 = 1.
    """
    return bool(
        _read_input_registers(
            modbus_client=modbus_client, address=Inputs.LSHH102A_IN.value,
            count=1
        )[0]
    )


def _search_top_switch(switches: list[bool], enabled: bool) -> int:
    """
    Search first from the top (highest) enabled or disabled electrolyte level
    switch.
    """
    return next(
        (
            len(switches) - index for index, switch in
            enumerate(reversed(switches), start=0) if switch is enabled
        ), 0
    )


def _electrolyte_level(
    modbus_client: client.ModbusClient, logging: bool = True
) -> ElectrolyteLevel:
    """
    Read and report electrolyte level.
    """

    switches: list[bool] = [
        _low_level_switch(modbus_client=modbus_client),
        _medium_level_switch(modbus_client=modbus_client),
        _high_level_switch(modbus_client=modbus_client),
        _very_high_level_switch(modbus_client=modbus_client)
    ]

    electrolyte_level: ElectrolyteLevel = ElectrolyteLevel(
        _search_top_switch(switches=switches, enabled=True)
    )

    if not all(switches_below_max := switches[:electrolyte_level.value]):
        top_disabled_level: ElectrolyteLevel = ElectrolyteLevel(
            _search_top_switch(
                switches=switches_below_max, enabled=False
            )
        )

        raise MaintenanceModeException(
            f'Detected enabled {electrolyte_level.name} level switch while at'
            f' least one switch below ({top_disabled_level.name} level) is'
            f' disabled. Please contact Enapter customer support.'
        )

    if logging:
        _print_cyan(
            text=f'{electrolyte_level.name} electrolyte level detected...'
        )

    return electrolyte_level


def _toggle_maintenance(
    modbus_client: client.ModbusClient, enable: bool
) -> None:
    """
    Write maintenance holding register, address is 1013. Register type is
    boolean, technically it's similar to uint16. We must write 1/0 to turn
    Maintenance mode on/off.
    """
    _write_single_register(
        modbus_client=modbus_client, address=Holdings.MAINTENANCE.value,
        value=int(enable)
    )


def _toggle_flushing(modbus_client: client.ModbusClient, enable: bool) -> None:
    """
    Write flushing holding register, address is 1015. Register type is
    boolean, technically it's similar to uint16. We must write 0/1 to turn
    flushing on/off (logic is reversed since in fact register means 'skip
    flushing').
    """
    _write_single_register(
        modbus_client=modbus_client, address=Holdings.FLUSHING.value,
        value=int(not enable)
    )


def _flushing_on(modbus_client: client.ModbusClient) -> None:
    """
    Turn flushing on.
    """
    print('Turning flushing on...')

    _toggle_flushing(modbus_client=modbus_client, enable=True)

    print('Successfully turned flushing on')


def _maintenance_on(
    modbus_client: client.ModbusClient, initial_state: State
) -> None:
    """
    Turn Maintenance mode on.
    """
    if initial_state is State.IDLE:
        print('Turning Maintenance mode on...')

        _toggle_maintenance(modbus_client=modbus_client, enable=True)

        if (
            state := _actual_state(modbus_client=modbus_client)
        ) is not State.MAINTENANCE_MODE:
            raise MaintenanceModeException(
                f'Got state {state.name} instead of '
                f'{State.MAINTENANCE_MODE.name}, please contact Enapter '
                f'customer support'
            )

        print('Successfully turned Maintenance mode on')

    else:
        print('Maintenance mode is already on')


def _maintenance_off(modbus_client: client.ModbusClient) -> None:
    """
    Turn Maintenance mode off.
    """
    print('Turning Maintenance mode off...')

    _toggle_maintenance(modbus_client=modbus_client, enable=False)

    if (state := _actual_state(modbus_client=modbus_client)) is not State.IDLE:
        raise MaintenanceModeException(
            f'Got state {state.name} instead of {State.IDLE.name}, please '
            f'contact Enapter customer support'
        )

    print('Successfully turned Maintenance mode off')


def _check_refilling_state(
    modbus_client: client.ModbusClient,
    expected_refilling_state: RefillingState
) -> None:
    """
    Check specific refilling state.
    """
    print('Checking refilling state...')

    if (
        actual_refilling_state := _actual_refilling_state(
            modbus_client=modbus_client
        )
    ) is not expected_refilling_state:
        raise MaintenanceModeException(
            f'Wrong refilling state detected, expected '
            f'{expected_refilling_state.name}, actual '
            f'{actual_refilling_state.name}. Please contact Enapter customer '
            f'support.'
        )

    _print_cyan(
        f'Detected expected {actual_refilling_state.name} refilling state\n'
    )


def _handle_very_high_electrolyte_level(
    modbus_client: client.ModbusClient, el_21: bool
) -> None:
    """
    Handle very high electrolyte level while refilling.
    """
    if _electrolyte_level(
        modbus_client=modbus_client, logging=False
    ) is ElectrolyteLevel.VERY_HIGH:
        _print_red(
            f'Detected {ElectrolyteLevel.VERY_HIGH.name} electrolyte level.'
        )

        if el_21:
            _wait_confirmation(
                prompt=(
                    f'Please drain electrolyte to {ElectrolyteLevel.HIGH.name}'
                    f' level.\nType {INPUT_CONFIRMATION} and press Enter to'
                    f' proceed:'
                )
            )

            _wait_electrolyte_level(
                modbus_client=modbus_client,
                expected_level=ElectrolyteLevel.HIGH, timeout=REFILLING_TIMEOUT
            )

        else:
            raise MaintenanceModeException(
                'Please contact Enapter customer support'
            )


def _perform_draining(modbus_client: client.ModbusClient) -> None:
    """
    Draining procedure with required checks.
    """
    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.DRAINING
    )

    print(
        '\n=================================================================\n'
        '============================ DRAINING ===========================\n\n'
    )
    _wait_confirmation(
        prompt=(
            f'Electrolyser is ready for draining.\nCurrent electrolyte level'
            f' will be reported every {ELECTROLYTE_PRESENCE_CHECK_TIMEOUT}'
            f' seconds until draining is complete.\nType {INPUT_CONFIRMATION}'
            f' and press Enter to proceed:'
        )
    )

    _wait_electrolyte_level(
        modbus_client=modbus_client,
        expected_level=ElectrolyteLevel.EMPTY, timeout=DRAINING_TIMEOUT
    )


def _perform_flushing(modbus_client: client.ModbusClient) -> None:
    """
    Flushing procedure with required checks.
    """
    print(
        '\n=================================================================\n'
        '============================ FLUSHING ===========================\n\n'
    )

    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.WAIT_FLUSHING
    )

    _wait_confirmation(
        prompt=(
            f'Flushing will be performed.\n'
            f'1. Disconnect pipe from FILL/DRAIN port\n'
            f'2. Connect water pipe\n'
            f'3. Type {INPUT_CONFIRMATION} and press Enter when ready:\n'
        )
    )

    _check_water_pipe_connection(
        modbus_client=modbus_client, expect_no_electrolyte=True
    )

    _wait_confirmation(
        prompt=(
            f'\nNow electrolyser will be automatically refilled with'
            f' water.\nCurrent electrolyte level will be reported every'
            f' {ELECTROLYTE_PRESENCE_CHECK_TIMEOUT} seconds until flushing is'
            f' complete.\nType {INPUT_CONFIRMATION} and press Enter to'
            f' proceed:'
        )
    )

    _flushing_on(modbus_client=modbus_client)

    _wait_electrolyte_level(
        modbus_client=modbus_client, expected_level=ElectrolyteLevel.HIGH,
        timeout=REFILLING_TIMEOUT, refilling=True
    )

    _check_refilling_warnings(modbus_client=modbus_client)

    _print_yellow(
        text=(
            'Now waiting until water is mixed with pump, this process will'
            ' be monitored automatically...'
        )
    )

    _wait_refilling_state(
        modbus_client=modbus_client, expected_state=RefillingState.DRAINING,
        timeout=_actual_refilling_mixing_time(modbus_client=modbus_client) * 2
    )

    _perform_draining(modbus_client=modbus_client)


def _perform_refilling(
    modbus_client: client.ModbusClient, el_21: bool = False
) -> None:
    """
    Refilling procedure with required checks.
    """
    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.MAINTENANCE
    )

    print(
        '\n=================================================================\n'
        '=========================== REFILLING ===========================\n\n'
    )

    refill_to_level: ElectrolyteLevel = (
        ElectrolyteLevel.HIGH if el_21 else ElectrolyteLevel.MEDIUM
    )

    electrolyte_type: str = (
        '3.6L of 1% KOH' if el_21 else '2L of 1.54% KOH'
    )

    _wait_confirmation(
        prompt=(
            f'1. Prepare electrolyte bag with {electrolyte_type} solution\n'
            f'2. Connect refilling pipe to FILL/DRAIN port\n'
            f'3. Type {INPUT_CONFIRMATION} and press Enter when ready:\n'
        )
    )
    _print_yellow(
        text=(
            f'Now carefully raise the electrolyte bag above the device to fill'
            f' to {ElectrolyteLevel.LOW.name} level.\nPlease don\'t fill more'
            f' at this step.'
        )
    )

    if not el_21:
        _print_red(text='WARNING! Overfill may damage Electrolyser!')

    _print_yellow(
        text=f'Waiting for {ElectrolyteLevel.LOW.name} level electrolyte...'
    )

    try:
        _wait_electrolyte_level(
            modbus_client=modbus_client, expected_level=ElectrolyteLevel.LOW,
            timeout=REFILLING_TIMEOUT, refilling=True
        )

    except HighElectrolyteLevelException:
        _print_yellow(
            f'Higher than {ElectrolyteLevel.LOW.name} electrolyte level'
            f' detected...'
        )

        _handle_very_high_electrolyte_level(
            modbus_client=modbus_client, el_21=el_21
        )

    else:
        _check_refilling_state(
            modbus_client=modbus_client,
            expected_refilling_state=RefillingState.KOH_REFILLING
        )

    finally:
        if el_21 and _electrolyte_level(
            modbus_client=modbus_client
        ).value < ElectrolyteLevel.HIGH.value:
            _check_refilling_state(
                modbus_client=modbus_client,
                expected_refilling_state=RefillingState.KOH_REFILLING
            )

    if _electrolyte_level(
        modbus_client=modbus_client
    ).value < refill_to_level.value:
        _print_yellow(
            text=(
                f'Now carefully raise the electrolyte bag above the device to'
                f' fill to {refill_to_level.name} level.\nPlease don\'t fill'
                f' more at this step.'
            )
        )

        if not el_21:
            _print_red(text='WARNING! Overfill may damage Electrolyser!')

        _print_yellow(
            text=f'Waiting for {refill_to_level.name} level electrolyte...'
        )

        try:
            _wait_electrolyte_level(
                modbus_client=modbus_client, expected_level=refill_to_level,
                timeout=REFILLING_TIMEOUT, refilling=True
            )

        except HighElectrolyteLevelException:
            _handle_very_high_electrolyte_level(
                modbus_client=modbus_client, el_21=el_21
            )

    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.KOH_REFILLING_FINISH
    )


def _finish_refilling(modbus_client: client.ModbusClient) -> None:
    """
    Finish refilling procedure with required checks.
    """
    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.SERVICE_REFILLING
    )

    _wait_electrolyte_level(
        modbus_client=modbus_client, expected_level=ElectrolyteLevel.HIGH,
        timeout=REFILLING_TIMEOUT, refilling=True
    )

    _print_yellow(
        text=(
            'Now waiting until water is mixed with pump, this process will be'
            ' monitored automatically...'
        )
    )

    _wait_refilling_state(
        modbus_client=modbus_client, expected_state=RefillingState.IDLE,
        timeout=_actual_refilling_mixing_time(modbus_client=modbus_client) * 2
    )

    _check_refilling_warnings(modbus_client=modbus_client)

    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.IDLE
    )


def _wait_electrolyte_level(
    modbus_client: client.ModbusClient, expected_level: ElectrolyteLevel,
    timeout: int, refilling: bool = False
) -> None:
    """
    Wait for specific electrolyte level.
    """
    wait_until: float = time.time() + timeout

    while time.time() < wait_until:
        if (
            electrolyte_level := _electrolyte_level(
                modbus_client=modbus_client
            )
        ) is expected_level:
            break

        elif (
            refilling and electrolyte_level.value > expected_level.value
        ):
            raise HighElectrolyteLevelException(
                f'Higher electrolyte level detected. Expected'
                f' {expected_level.name}, actual {electrolyte_level.name}. If'
                f' this happened during automatic refilling, please contact'
                f' Enapter customer support.'
            )

        time.sleep(ELECTROLYTE_PRESENCE_CHECK_TIMEOUT)

    else:
        raise MaintenanceModeException(
            f'Failed to wait for {expected_level.name} level during'
            f' {timeout // 60} minutes.'
        )


def _wait_refilling_state(
    modbus_client: client.ModbusClient, expected_state: RefillingState,
    timeout: int
) -> None:
    """
    Wait for specific refilling state.
    """
    wait_until: float = time.time() + timeout

    while time.time() < wait_until:
        if _actual_refilling_state(
            modbus_client=modbus_client
        ) is expected_state:
            break

        time.sleep(REFILLING_STATE_CHECK_TIMEOUT)

    else:
        raise MaintenanceModeException(
            f'Failed to wait for {expected_state.name} refilling state during'
            f' {timeout} seconds.'
        )


def _check_water_pipe_connection(
    modbus_client: client.ModbusClient, expect_no_electrolyte: bool = False,
    attempts: int = MAX_WATER_PIPE_CONNECT_ATTEMPTS
) -> None:
    """
    Ensure that water pipe is connected properly. Check pressure and
    electrolyte presence if necessary.
    """
    water_pipe_connect_attempts: int = 0

    pressure_ok: bool = False
    electrolyte_ok: bool = False

    min_pressure: float = _actual_refilling_min_water_pressure(
        modbus_client=modbus_client
    )

    max_pressure: float = _actual_refilling_max_water_pressure(
        modbus_client=modbus_client
    )

    while water_pipe_connect_attempts < attempts:
        print('Now checking water inlet pressure...')

        if (
            min_pressure < (
                actual_water_inlet_pressure := _actual_water_inlet_pressure(
                    modbus_client=modbus_client
                )
            ) < max_pressure
        ):
            pressure_ok = True

            print('Pressure is OK')

        else:
            _print_yellow(
                text=(
                    f'Water inlet pressure {actual_water_inlet_pressure} is'
                    f' not in allowed bounds ({min_pressure}, {max_pressure})'
                )
            )

        if expect_no_electrolyte:
            print('Now re-checking electrolyte presence...')

            if _electrolyte_level(
                modbus_client=modbus_client
            ) is ElectrolyteLevel.EMPTY:
                print('Electrolyte is OK')

                electrolyte_ok = True

            else:
                _print_yellow(
                    text=(
                        'Electrolyte presence detected. This is normal and may'
                        ' occur while attaching a water pipe'
                    )
                )

                _perform_draining(modbus_client=modbus_client)

                _check_refilling_state(
                    modbus_client=modbus_client,
                    expected_refilling_state=RefillingState.WAIT_FLUSHING
                )

        else:
            electrolyte_ok = True

        if pressure_ok and electrolyte_ok:
            break

        _wait_confirmation(
            prompt=(
                f'Problems with water pipe detected.\nPlease double check'
                f' water pipe, type {INPUT_CONFIRMATION} and press Enter when'
                f' ready:\n'
            )
        )

        water_pipe_connect_attempts += 1

    else:
        raise WaterPipeException(
            f'Water pipe problems detected after {attempts} connection'
            f' attempt{"s" if attempts > 1 else ""}. Please contact Enapter'
            f' customer support'
        )


def _wait_confirmation(prompt: str) -> None:
    """
    Print prompt and wait for user confirmation.
    """
    print(prompt)

    while input().upper() != INPUT_CONFIRMATION:
        _print_yellow(text='Wrong confirmation')


def _run_maintenance_21(
    modbus_client: client.ModbusClient, initial_state: State
) -> None:
    """
    Run Maintenance actions for EL2.1.
    """
    print('Running Maintenance for EL2.1...')

    _maintenance_on(modbus_client=modbus_client, initial_state=initial_state)

    match actual_refilling_state := _actual_refilling_state(
        modbus_client=modbus_client
    ):
        case RefillingState.DRAINING:
            draining_required: bool = True

        case RefillingState.MAINTENANCE:
            draining_required: bool = False

            print(
                'Seems like it\'s first refilling. Draining procedure will be'
                ' skipped.'
            )

        case _:
            raise MaintenanceModeException(
                f'Got unexpected refilling state'
                f' {actual_refilling_state.name}, please contact Enapter'
                f' customer support'
            )

    if draining_required:
        _perform_draining(modbus_client=modbus_client)

    _perform_refilling(modbus_client=modbus_client, el_21=True)

    _check_refilling_warnings(modbus_client=modbus_client)

    _maintenance_off(modbus_client=modbus_client)

    _check_refilling_state(
        modbus_client=modbus_client,
        expected_refilling_state=RefillingState.IDLE
    )


def _run_maintenance_4x(
    modbus_client: client.ModbusClient, initial_state: State
) -> None:
    """
    Run Maintenance actions for EL4.x.
    """
    print('Running Maintenance for EL4.x...')

    _maintenance_on(modbus_client=modbus_client, initial_state=initial_state)

    match actual_refilling_state := _actual_refilling_state(
        modbus_client=modbus_client
    ):
        case RefillingState.DRAINING:
            draining_required: bool = True
            flushing_required: bool = True

        case RefillingState.WAIT_FLUSHING:
            draining_required: bool = False
            flushing_required: bool = True

        case RefillingState.MAINTENANCE:
            draining_required: bool = False
            flushing_required: bool = False

            print(
                'Seems like it\'s first refilling. Draining and flushing'
                ' procedures will be skipped.'
            )

        case _:
            raise MaintenanceModeException(
                f'Got unexpected refilling state'
                f' {actual_refilling_state.name}, please contact Enapter'
                f' customer support'
            )

    if draining_required:
        _perform_draining(modbus_client=modbus_client)

    # Handle situation when script was somehow interrupted and flushing is
    # already complete.
    if _actual_refilling_state(
        modbus_client=modbus_client
    ) is RefillingState.MAINTENANCE:
        flushing_required = False

    if flushing_required:
        _perform_flushing(modbus_client=modbus_client)

    _perform_refilling(modbus_client=modbus_client)

    _wait_confirmation(
        prompt=(
            f'Now Maintenance mode will be turned off. Check that water pipe'
            f' is connected to finish refilling automatically.\nType'
            f' {INPUT_CONFIRMATION} and press Enter when ready:'
        )
    )

    _maintenance_off(modbus_client=modbus_client)

    try:
        _check_water_pipe_connection(modbus_client=modbus_client, attempts=1)

    except WaterPipeException:
        _print_yellow(
            f'Failed to fill water to {ElectrolyteLevel.HIGH} level.\nPlease'
            f' make sure that water pipe is connected properly.\nAfter pipe is'
            f' OK, water will be added automatically when required.'
        )

    else:
        _finish_refilling(modbus_client=modbus_client)


def _run_maintenance(
    modbus_client: client.ModbusClient, initial_state: State
) -> None:
    """
    Run actions required for Maintenance mode depending on initial state and
    electrolyser model.
    """

    # Read and decode ProjectId input register, address is 0. Register type is
    # uint32, so number of registers to read is 32 / 16 = 2. First convert raw
    # response to single int value with pyModbusTCP utils.
    converted_device_model: int = utils.word_list_to_long(
        val_list=_read_input_registers(
            modbus_client=modbus_client, address=Inputs.DEVICE_MODEL.value,
            count=2
        )
    )[0]

    # Decode converted int to human-readable device model.
    match DeviceModel(
        decoded_device_name := bytes.fromhex(
            f'{converted_device_model:x}'
        ).decode()
    ):
        case DeviceModel.EL21:
            _run_maintenance_21(
                modbus_client=modbus_client, initial_state=initial_state
            )

        case DeviceModel.EL40 | DeviceModel.ES40 | DeviceModel.ES41:
            _run_maintenance_4x(
                modbus_client=modbus_client, initial_state=initial_state
            )

        case _:
            raise MaintenanceModeException(
                f'Got unknown device model: {decoded_device_name}, please '
                f'contact Enapter customer support.'
            )

    print('Maintenance mode completed OK')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run EL maintenance with Modbus'
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

    if sys.platform == WIN32:
        # Enable colored output for Windows console
        os.system('color')

    if input(
        _text_color(
            text=(
                'WARNING! Please read carefully!\nThis script turns'
                f' Maintenance mode on.\nMaintenance mode requires manual'
                f' actions with electrolyser such as electrolyte draining,'
                f' flushing (for EL4.x) and refilling.\nIf you fill'
                f' electrolyte for the first time, only refilling is required.'
                f'\nIf at some step electrolyte level is reported incorrectly,'
                f' it may indicate hardware problems.\nIn this case terminate'
                f' script with Ctrl+C and contact Enapter customer support.\n'
                f'Script will be terminated anyway if draining/refilling is'
                f' not complete during'
                f' {DRAINING_TIMEOUT // 60}/{REFILLING_TIMEOUT // 60} minutes'
                f' correspondingly.\nType {INPUT_CONFIRMATION} and press Enter'
                f' if you really want to continue. Press Ctrl+С or Enter to'
                f' exit:\n'
            ), color=ConsoleColor.RED
        )
    ).upper() != INPUT_CONFIRMATION:
        sys.exit('Maintenance mode script execution stopped by user')

    args: argparse.Namespace = parse_args()

    modbus_client: client.ModbusClient = client.ModbusClient(
        host=args.modbus_ip, port=args.modbus_port
    )

    try:
        _print_yellow('Checking if Maintenance can be performed...')

        if _electrolyte_level(
            modbus_client=modbus_client
        ) is ElectrolyteLevel.VERY_HIGH:
            sys.exit(
                'Very High Electrolyte Level Switch is enabled, Maintenance'
                ' mode can\'t be turned on.\nIf you use Electrolyser 2.1,'
                ' please drain some electrolyte, reboot device and run script'
                ' again.\nOtherwise please contact Enapter customer support.'
            )

        if (state := _actual_state(modbus_client=modbus_client)) not in (
            State.IDLE, State.MAINTENANCE_MODE
        ):
            sys.exit(
                f'Electrolyser state is {state.name}, can\'t turn Maintenance'
                f' mode on. Switch electrolyser to either {State.IDLE.name} or'
                f' {State.MAINTENANCE_MODE.name} and run script again.'
            )

        _print_yellow(text='Conditions for Maintenance are OK')

        _run_maintenance(modbus_client=modbus_client, initial_state=state)

    except Exception as e:
        # If something went wrong, we can access Modbus error/exception info.
        # For example, in case of connection problems, reading register will
        # return None and script will fail with error while data converting,
        # but real problem description will be stored in client.
        print(f'Exception occurred: {e}')
        print(f'Modbus error: {modbus_client.last_error_as_txt}')
        print(f'Modbus exception: {modbus_client.last_except_as_txt}')

        active_errors: str = (
            ', '.join(
                _decode_errors(modbus_client=modbus_client)
            ) or 'No errors'
        )

        active_warnings: str = (
            ', '.join(
                _decode_warnings(modbus_client=modbus_client)
            ) or 'No warnings'
        )

        _print_red(
            text=(
                f'Please provide the following errors and warnings to Enapter'
                f' customer support:\nErrors: {active_errors}\nWarnings: '
                f'{active_warnings}\nEvents description is available at'
                f' https://handbook.enapter.com'
            )
        )

        raise


if __name__ == '__main__':
    main()
