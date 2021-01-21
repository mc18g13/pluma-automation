import datetime
from abc import ABC, abstractclassmethod, abstractstaticmethod
from typing import Sequence, TYPE_CHECKING, List
# Fix circular dependencies
if TYPE_CHECKING:
    from pluma.test.testbase import TestBase
    from pluma.cli import Configuration

# TODO: The session parameter should be an instance of a metadata class (such as Session, which
# is currently WIP) instead of a TestBase iterable.
# TODO: the result_pass and result_message should be collected into a result object. This result
# object should also include other possible states for the test (ignored, skipped, etc.)
# TODO: Should there be a session_result paramter in report_session_end?


class ReporterBase(ABC):
    """ Base class for output and status reporters """

    @abstractstaticmethod
    def configuration_key() -> str:
        """ Configuration key to be used to configure this reporter """

    @abstractstaticmethod
    def display_name() -> str:
        """ Display name for this reporter """

    @abstractclassmethod
    def from_configuration(cls, config: 'Configuration') -> 'ReporterBase':
        """ Create a reporter from a configuration object """

    def _report_session_start(self, time: datetime.datetime, session: Sequence['TestBase']) -> None:
        """Report the start of a testing session"""

    def _report_session_end(self, time: datetime.datetime, session: Sequence['TestBase']) -> None:
        """Report the end of a testing session"""

    def _report_test_start(self, time: datetime.datetime, session: Sequence['TestBase'],
                           test: 'TestBase') -> None:
        """Report the start of a single test"""

    def _report_test_end(self, time: datetime.datetime, session: Sequence['TestBase'],
                         test: 'TestBase', result_passed: bool, result_message: str) -> None:
        """Report the end of a single test"""

    @staticmethod
    def report_session_start(reporters: 'List[ReporterBase]', time: datetime.datetime,
                             session: Sequence['TestBase']) -> None:
        # pylint: disable=protected-access
        for reporter in reporters:
            reporter._report_session_start(time, session)

    @staticmethod
    def report_session_end(reporters: 'List[ReporterBase]', time: datetime.datetime,
                           session: Sequence['TestBase']) -> None:
        # pylint: disable=protected-access
        for reporter in reporters:
            reporter._report_session_end(time, session)

    @staticmethod
    def report_test_start(reporters: 'List[ReporterBase]', time: datetime.datetime,
                          session: Sequence['TestBase'], test: 'TestBase') -> None:
        # pylint: disable=protected-access
        for reporter in reporters:
            reporter._report_test_start(time, session, test)

    @staticmethod
    def report_test_end(reporters: 'List[ReporterBase]', time: datetime.datetime,
                        session: Sequence['TestBase'], test: 'TestBase', result_passed: bool,
                        result_message: str) -> None:
        # pylint: disable=protected-access
        for reporter in reporters:
            reporter._report_test_end(time, session, test, result_passed, result_message)
