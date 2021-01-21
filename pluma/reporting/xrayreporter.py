import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
from pluma.test.testbase import TestBase
from pluma.reporting.xrayhelper import JiraXrayHelper, JiraResult, JiraTestPlanIssue
from pluma.core.baseclasses import Logger, ReporterBase
from pluma.cli.config import Configuration

# TODO: store test XRAY IDs so we don't have to search for them every time we update them.
# In addition, we should really only be pushing updates to the tests that changed.
# TODO: Figure out what test metadata we have and what we need to generate. In addition,
# figure out where this reporter should hook into the TestRunner/TestController, and how
# that metadata is going to get piped.
# TODO: It might make more sense to implement this integration using the XRay GraphQL API,
# seeing as we are performing a lot searching.
# TODO: XRay steps depending on the structure of each test?
# TODO: Figure out how to unit test this

PLUMA_PLAN_TITLE = "Pluma autogenerated test plan"
PLUMA_EXEC_SUMMARY_PREFIX = "Pluma autogenerated test execution starting at "

log = Logger()


@dataclass
class _XRayReportingSession:
    plan: Optional[JiraTestPlanIssue] = None
    execution_key: Optional[str] = None
    execution_metadata: Dict[str, str] = field(default_factory=dict)
    execution_test_metadata: List[JiraResult] = field(default_factory=list)


class XRayReporter(ReporterBase):
    """ XRay Cloud reporter, ported from PlanRunner """
    @staticmethod
    def configuration_key() -> str:
        return 'xray'

    @staticmethod
    def display_name() -> str:
        return 'XRay Cloud'

    @classmethod
    def from_configuration(cls, config: Configuration) -> 'XRayReporter':
        return cls(jira_project_key=config.pop(str, 'jira_project_key'),
                   jira_url=config.pop(str, 'jira_url'),
                   jira_username=config.pop(str, 'jira_username'),
                   jira_password=config.pop(str, 'jira_password'),
                   xray_client_id=config.pop(str, 'xray_client_id'),
                   xray_client_secret=config.pop(str, 'xray_client_secret'),
                   test_plan_name=config.pop(str, 'test_plan_name'))

    def __init__(self, jira_project_key: str, jira_url: str, jira_username: str, jira_password: str,
                 xray_client_id: str, xray_client_secret: str, test_plan_name: str):
        self.test_plan_name = test_plan_name
        self._xray_helper = JiraXrayHelper(project_key=jira_project_key,
                                           jira_url=jira_url,
                                           xray_client_id=xray_client_id,
                                           xray_client_secret=xray_client_secret,
                                           jira_user=jira_username,
                                           jira_password=jira_password)
        self._reporting_session: Optional[_XRayReportingSession] = None

    def _push_running_execution_plan_to_xray(self, tests_to_push: List[JiraResult]):
        self._reporting_session.execution_key = self._xray_helper.create_or_update_test_execution(
            self._reporting_session.plan,
            self._reporting_session.execution_metadata,
            tests_to_push,
            cur_execution_key=self._reporting_session.execution_key
        )

    @staticmethod
    def _pluma_test_to_jira_test(test: TestBase, start_time: datetime.datetime,
                                 end_time: Optional[datetime.datetime] = None) -> JiraResult:
        return JiraResult(name=str(test), summary=str(test), status='TODO', startDate=start_time,
                          stopDate=end_time if end_time else start_time + datetime.timedelta(1))

    def _get_running_test_meta(self, test: TestBase) -> Optional[JiraResult]:
        for test_meta in self._reporting_session.execution_test_metadata:
            if test_meta.name == str(test):
                return test_meta
        return None

    def _report_session_start(self, time: datetime.datetime, session: Sequence[TestBase]):
        start_time_str = JiraXrayHelper.date_to_xray_format(time)
        end_time_str = JiraXrayHelper.date_to_xray_format(time + datetime.timedelta(1))
        execution_metadata = {
            "summary": f"{PLUMA_EXEC_SUMMARY_PREFIX} {start_time_str}",
            "description": "",
            "startDate": start_time_str,
            # Guess the end date? Apparently it's a "predicted" value
            "finishDate": end_time_str,
        }
        self._reporting_session = _XRayReportingSession(
            plan=self._xray_helper.create_or_update_plan(self.test_plan_name, PLUMA_PLAN_TITLE),
            execution_test_metadata=[self._pluma_test_to_jira_test(test, time) for test in session],
            execution_metadata=execution_metadata)
        if self._reporting_session.plan is None:
            raise RuntimeError(
                'Unable to create or update the XRay test plan, check your credentials.')
        self._push_running_execution_plan_to_xray(
            self._reporting_session.execution_test_metadata)

    def _report_session_end(self, time: datetime.datetime, session):
        self._reporting_session.execution_metadata["finishDate"] = JiraXrayHelper.date_to_xray_format(
            time)
        self._push_running_execution_plan_to_xray(self._reporting_session.execution_test_metadata)
        self._reporting_session = None

    def _report_test_start(self, time: datetime.datetime, session, test: TestBase):
        if self._reporting_session is None:
            raise RuntimeError(
                f'Reporting for test start for test {test} called before session start')
        running_test_meta = self._get_running_test_meta(test)
        if running_test_meta is None:
            log.warning(
                f'Xray reporter got an unrecognized test name {test} on report_test_start hook, '
                'not reporting it.'
            )
            return
        running_test_meta.status = 'EXECUTING'

    def _report_test_end(self, time: datetime.datetime, session: Sequence[TestBase], test: TestBase,
                         result_passed: bool, result_message: str):
        if self._reporting_session is None:
            raise RuntimeError(
                f'Reporting for test end for test {test} called before session start')
        running_test_meta = self._get_running_test_meta(test)
        if running_test_meta is None:
            log.warning(
                f'Xray reporter got an unrecognized test name {test} on report_test_start hook, '
                ' not reporting it.'
            )
            return
        running_test_meta.status = 'PASSED' if result_passed else 'FAILED'
        running_test_meta.comment = result_message
