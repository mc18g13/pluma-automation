import traceback
import time
import datetime
from abc import ABC, abstractmethod
from copy import copy
from typing import Iterable, Optional, List, Union

from pluma.core.board import Board
from pluma import utils
from pluma.core.baseclasses import LogLevel, Logger, ReporterBase
from pluma.test import TestBase, TestingException, AbortTesting

global_logger = Logger()


class TestRunnerBase(ABC):
    '''Run a set of tests a single time and collect their settings and saved data'''

    def __init__(self, board: Board = None, tests: Union[TestBase, Iterable[TestBase]] = None,
                 email_on_fail: bool = None, continue_on_fail: bool = None):
        self.board = board
        self.email_on_fail = email_on_fail if email_on_fail is not None else False
        self.continue_on_fail = continue_on_fail if continue_on_fail is not None else False
        self.test_fails = []

        # Use global logger if no board available
        if board:
            self.log = self.board.log
            self.hold_log = self.board.hold_log
            self.release_log = self.board.release_log
        else:
            self.log = global_logger.log
            self.hold_log = global_logger.hold
            self.release_log = global_logger.release

        self._tests = []
        if isinstance(tests, TestBase):
            tests = [tests]
        self.tests = tests

        self.known_tasks = TestBase.task_hooks

        # General purpose data for use globally between tests
        self.data = {}

    @abstractmethod
    def _run(self, tests: Iterable[TestBase], reporters: Optional[List[ReporterBase]] = None) -> bool:
        '''Run the tests'''

    def run(self, reporters: Optional[List[ReporterBase]] = None) -> bool:
        '''Run all tasks for all tests. Returns True if all succes and False otherwise'''
        self.log('Running tests', bold=True)
        self.test_fails = []

        # Init data
        self.data = {}

        # Init test data
        for test in self.tests:
            self._init_test_data(test)

        if reporters:
            self.log(f"Running reporters: {[r.display_name() for r in reporters]}", bold=True)
            start = datetime.datetime.now()
            ReporterBase.report_session_start(reporters, start, self.tests)

        self.log("Running tests: {}".format(
            list(map(str, self.tests))), level=LogLevel.DEBUG)

        try:
            # Defer the actual test running to classes that inherit this base
            self._run(self.tests, reporters=reporters)
        # Prevent exceptions from leaving test runner
        except Exception:
            self.log("\n== TESTING ABORTED EARLY ==", color='red', bold=True)
        else:
            self.log("\n== ALL TESTS COMPLETED ==", color='blue', bold=True,
                     level=LogLevel.DEBUG)

        if reporters:
            end = datetime.datetime.now()
            self.log(f"Running reporters: {[r.display_name() for r in reporters]}", bold=True)
            ReporterBase.report_session_end(reporters, end, self.tests)

        # Check if any tasks failed
        return not self.test_fails

    def __call__(self):
        return self.run()

    def __repr__(self):
        return f'[{self.__class__.__name__}]'

    @property
    def num_tests(self):
        return len(self.tests)

    def _init_test_data(self, test: TestBase):
        '''Initialise the test data. Required for integration with TestController'''
        test.data = {}
        self.data[str(test)] = {
            'tasks': {
                'ran': [],
                'failed': {}
            },
            'data': test.data,
            'settings': test.settings,
            'order': self.tests.index(test)
        }

    @property
    def tests(self) -> List[TestBase]:
        return self._tests

    @tests.setter
    def tests(self, tests: List[TestBase]):
        self._tests = []
        for test in tests:
            self.add_test(test)

    def add_test(self, test: TestBase):
        '''Add a test to the test list. Handles tests with same name by appending a number'''
        # Verify that test is an instance of class TestBase.
        if not isinstance(test, TestBase):
            raise AttributeError(
                'test should be an object instance of class TestBase'
                ' or one of its subclasses.'
            )

        if self._get_test_by_name(str(test)) is not None:
            raise RuntimeError(f'Found duplicate test name {str(test)}!'
                               'This is a bug, please report it to the pluma development team.')

        test = copy(test)

        self.log("Appending test: {}".format(str(test)))
        self._tests.append(test)

    def rm_test(self, test: TestBase):
        '''Remove a test from the test list'''
        if test in self.tests:
            self.log("Removed test: {}".format(str(test)))
            self.tests.remove(test)

    def _get_test_by_name(self, test_name: str) -> Optional[TestBase]:
        tests = [t for t in self.tests if str(t) == test_name]
        if len(tests) > 1:
            raise TestingException('Found multiple tests with name {}'.format(
                test_name))

        return None if not tests else tests[0]

    def _run_tasks(self,
                   tests: Union[TestBase, Iterable[TestBase]],
                   task_names: Union[str, List[str]],
                   reporters: Optional[List[ReporterBase]] = None
                   ):
        '''Run all tasks in task_names on test in tests if the test has a task with that name'''
        if isinstance(task_names, str):
            task_names = [task_names]

        if not isinstance(tests, Iterable):
            tests = [tests]

        for test, task in ((test, task)
                           for task in task_names
                           for test in tests
                           if hasattr(test, task)):
            self._run_task(task, test, reporters=reporters)

    def _run_task(self, task_name, test: TestBase, reporters: Optional[List[ReporterBase]] = None):
        '''Run a single task from a test'''
        task_func = getattr(test, task_name, None)
        if not task_func:
            # If test does not have this task, then skip
            return

        self.data[str(test)]['tasks']['ran'].append(task_name)

        if reporters:
            start = datetime.datetime.now()
            ReporterBase.report_test_start(reporters, start, self.tests, test)

        # Print test message
        test_message = f'{str(test)} - {task_name}'

        column_limit = 75
        if len(test_message) > column_limit:
            test_message = f'{test_message[:column_limit-3]}...'

        self.log(test_message.ljust(column_limit) + ' ',
                 level=LogLevel.IMPORTANT, newline=False)
        self.hold_log()

        did_pass = False
        try:
            task_func()
        # If exception is one we deliberately caused, don't handle it
        except KeyboardInterrupt as e:
            raise e
        except InterruptedError as e:
            raise e
        except Exception as e:
            self.data[str(test)]['tasks']['failed'][task_name] = str(e)

            self.log('FAIL', color='red', level=LogLevel.IMPORTANT, bypass_hold=True)

            # Run teardown for test if test_body raises an exception
            if hasattr(test, 'teardown') and task_name == 'test_body':
                self._run_task('teardown', test)

            # If request to abort testing, do so but don't run side effects and always reraise
            if isinstance(e, AbortTesting):
                self.log('Testing aborted by task {} - {}: {}'.format(
                    str(test), task_name, str(e)))
                raise e

            self._handle_failed_task(test, task_name, e)

            if not self.continue_on_fail:
                raise e

        else:
            self.log('PASS', color='green', level=LogLevel.IMPORTANT, bypass_hold=True)
            did_pass = True
        finally:
            self.release_log()

            # TODO: report a message from the test?
            if reporters:
                end = datetime.datetime.now()
                ReporterBase.report_test_end(reporters, end, self.tests, test, did_pass, '')

    def _handle_failed_task(self, test: TestBase, task_name: str, exception: Exception):
        '''Run any side effects for a task failure, such as writing logs or sending emails'''
        failed = {
            'time': time.time(),
            'test': test,
            'task': task_name,
            'exception': exception,
            'traceback': traceback.format_exc()
        }
        self.test_fails.append(failed)

        if self.email_on_fail:
            self.send_fail_email(exception, test, task_name)

        error = str(exception)
        if not error:
            error = exception.__class__.__name__

        self.log(f'Task failed: {error}', level=LogLevel.ERROR,
                 bold=True, color='red')
        self.log(f'Details: {failed}', color='yellow')

    def send_fail_email(self, exception: Exception, test_failed: TestBase, task_failed: str):
        '''Send an email to the default email address explaining the test failure'''
        subject = 'TestRunner Exception Occurred: [{}: {}] [{}]'.format(
            str(test_failed), task_failed, self.board.name if self.board else 'No Board')
        body = '''
        <b>Tests:</b> {}<br>
        <b>Test Failed:</b> {}<br>
        <b>Task Failed:</b> {}
        '''.format(
            [str(t) for t in self.tests],
            str(test_failed),
            task_failed)

        utils.send_exception_email(
            exception=exception,
            board=self.board,
            subject=subject,
            prepend_body=body
        )


class TestRunner(TestRunnerBase):
    '''Run a set of tests sequentially'''

    def _run(self, tests: Iterable[TestBase], reporters: Optional[List[ReporterBase]] = None):
        self.log('== TESTING MODE: SEQUENTIAL ==', color='blue', bold=True,
                 level=LogLevel.DEBUG)

        for test in tests:
            for task_name in self.known_tasks:
                self._run_tasks(test, task_name, reporters=reporters)


class TestRunnerParallel(TestRunnerBase):
    '''Run a set of tests in parallel'''

    def _run(self, tests: Iterable[TestBase], reporters: Optional[List[ReporterBase]] = None):
        self.log('== TESTING MODE: PARALLEL ==', color='blue', bold=True,
                 level=LogLevel.DEBUG)
        self._run_tasks(tests, self.known_tasks, reporters=reporters)
