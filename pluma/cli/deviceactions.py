import os
import sys
import time

from typing import List, Union

from pluma.core.baseclasses import Logger, LogLevel
from pluma import Board
from pluma.test import TaskFailed
from pluma.cli import DeviceActionBase, DeviceActionRegistry

log = Logger()


@DeviceActionRegistry.register('power_on')
class PowerOnAction(DeviceActionBase):
    def execute(self):
        self.board.power.on()


@DeviceActionRegistry.register('power_off')
class PowerOffAction(DeviceActionBase):
    def execute(self):
        self.board.power.off()


@DeviceActionRegistry.register('power_cycle')
class PowerCycleAction(DeviceActionBase):
    def __init__(self, board: Board, off_duration_ms: float = None):
        super().__init__(board)
        self.off_duration_ms = off_duration_ms or 1000

    def execute(self):
        self.board.power.off()
        time.sleep(self.off_duration_ms / 1000)
        self.board.power.on()


@DeviceActionRegistry.register('login')
class LoginAction(DeviceActionBase):
    def execute(self):
        self.board.login()


@DeviceActionRegistry.register('wait')
class WaitAction(DeviceActionBase):
    '''Delays the execution of the next test/action for a set amount of time'''

    def __init__(self, board: Board, duration: int):
        super().__init__(board)
        self.duration = duration

        if self.duration < 0:
            DeviceActionBase.parsing_error('Wait duration must be a positive number, '
                                           'but got "{self.duration}" instead.')

    def validate(self):
        return self.duration >= 0

    def execute(self):
        time.sleep(self.duration)


@DeviceActionRegistry.register('wait_for_pattern')
class WaitForPatternAction(DeviceActionBase):
    def __init__(self, board: Board, pattern: Union[str, List[str]], timeout: int = None):
        super().__init__(board)
        self.pattern = pattern if isinstance(pattern, List) else [pattern]
        self.timeout = timeout if timeout else 15

    def execute(self):
        self.board.console.read_all()
        matched_output = self.board.console.wait_for_match(match=self.pattern,
                                                           timeout=self.timeout)
        if not matched_output:
            raise TaskFailed(
                f'{str(self)}: Timeout reached while waiting for pattern "{self.pattern}"')


@DeviceActionRegistry.register('set')
class SetAction(DeviceActionBase):
    '''Sets the type of console to use'''

    def __init__(self, board: Board, device_console: str = None):
        super().__init__(board)

        self.device_console = device_console

        if self.device_console and not self.board.get_console(self.device_console):
            raise ValueError(f'Cannot set console to "{self.device_console}": '
                             'no such console was set for this board')

    def execute(self):
        if self.device_console:
            log.log(f'Setting device console to {self.device_console}')
            console = self.board.get_console(self.device_console)
            if not console:
                raise TaskFailed('Failed to find console "{self.device_console}"')

            self.board.console = console


@DeviceActionRegistry.register('deploy')
class DeployAction(DeviceActionBase):
    def __init__(self, board: Board, files: List[str], destination: str, timeout: int = 15):
        super().__init__(board)
        if not isinstance(files, list):
            raise ValueError(f'"files" must be a list, but instead got: {files}')

        self.files = files
        self.destination = destination
        self.timeout = timeout

    def execute(self):
        if not self.board.console.support_file_copy:
            raise TaskFailed('Cannot deploy files, current console does not support file copy. '
                             'Use or set a different console to be able to deploy files (e.g. SSH)')

        for f in self.files:
            log.log(f'Copying {f} to target device destination {self.destination}')
            self.board.console.copy_to_target(source=f, destination=self.destination,
                                              timeout=self.timeout)


class ManualDeviceActionBase(DeviceActionBase):
    '''Base class for manual tests'''

    def __init__(self, board: Board, message: str, name: str = None):
        super().__init__(board, test_name=name)
        self.manual_test_name = name
        self.message = message

        if not sys.__stdin__.isatty():
            raise ValueError('Non-interactive shell detected: '
                             'Manual actions must be used in an interactive shell')


@DeviceActionRegistry.register('manual_action')
class ManualDeviceAction(ManualDeviceActionBase):
    '''Print a message, and wait for the user to press ENTER'''

    def __init__(self, board: Board, message: str, name: str = None):
        super().__init__(board, message=message, name=name)

    def execute(self):
        if self.manual_test_name:
            test_title = f'Manual action "{self.manual_test_name}"'
        else:
            test_title = 'Manual action'

        log.log(f'{os.linesep}{test_title}:'
                f'{os.linesep}  > {self.message}'
                f'{os.linesep}Press ENTER when done',
                level=LogLevel.INFO, bypass_hold=True, newline=False)
        input()


@DeviceActionRegistry.register('manual_test')
class ManualTestDeviceAction(ManualDeviceActionBase):
    '''Print a message, expected behavior, and wait for user's feedback'''

    def __init__(self, board: Board, message: str, expected: str, name: str = None):
        super().__init__(board, message=message, name=name)
        self.expected = expected

    def execute(self):
        entered = None

        if self.manual_test_name:
            test_title = f'Manual test "{self.manual_test_name}"'
        else:
            test_title = 'Manual test'

        while (entered not in ['y', 'n']):
            log.log(f'{os.linesep}{test_title}:'
                    f'{os.linesep}  > {self.message}'
                    f'{os.linesep}  > Expected: {self.expected}'
                    f'{os.linesep}Was the test successful? [y/n]: ',
                    level=LogLevel.INFO, bypass_hold=True, newline=False)
            entered = input().lower()

        log.log(f'The user entered: "{entered}"', level=LogLevel.INFO,
                bypass_hold=True)
        log.log('Comments: ', level=LogLevel.INFO, bypass_hold=True, newline=False)
        comments = input()
        log.log(f'The user entered: "{comments}"',
                level=LogLevel.INFO, bypass_hold=True)

        if entered != 'y':
            raise TaskFailed('Manual test failed')
