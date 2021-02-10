import os
import yaml
from typing import List, Optional, Union, cast, Type

from pluma.cli.resultsconfig import ResultsConfig
from pluma.core.baseclasses import Logger, LogLevel, ReporterBase
from pluma.test import TestController, TestRunner, TestBase
from pluma.test.stock.deffuncs import sc_run_n_iterations
from pluma.cli import Configuration, ConfigurationError, TestsConfigError, TestDefinition,\
    TestsProvider
from pluma.core import Board
from pluma.utils.helpers import get_file_and_line

log = Logger()

SETTINGS_SECTION = 'settings'
RESULTS_SECTION = 'results'


class TestsConfig:
    def __init__(self, config: Configuration, test_providers: List[TestsProvider],
                 reporters: Optional[List[Type[ReporterBase]]] = None):
        reporters = reporters or []
        if not config or not isinstance(config, Configuration):
            raise ValueError(
                f'Null or invalid \'config\', which must be of type \'{Configuration}\'')

        if not test_providers:
            raise ValueError('Null test providers passed')

        if not isinstance(test_providers, list):
            test_providers = [test_providers]

        self.settings_config = config.pop_optional(Configuration, SETTINGS_SECTION,
                                                   Configuration())
        self.results_config = self.settings_config.pop_optional(Configuration, RESULTS_SECTION,
                                                                Configuration())
        self.test_providers: List[TestsProvider] = test_providers
        self.reporters = self._generate_reporters(self.settings_config, reporters)
        self.tests: List[TestDefinition]
        self.__populate_tests(config)

        config.ensure_consumed()

    def create_test_controller(self, board: Board) -> TestController:
        '''Create a TestController from the configuration, and Board'''
        if not board or not isinstance(board, Board):
            raise ValueError(
                f'Null or invalid \'board\', which must be of type \'{Board}\'')

        settings = self.settings_config

        try:
            controller = self._create_test_controller(board, settings)
            settings.ensure_consumed()
        except ConfigurationError as e:
            raise TestsConfigError(e)
        else:
            return controller

    def _create_test_controller(self, board: Board, settings: Configuration) -> TestController:
        tests = TestsConfig.create_tests(self.selected_tests(), board)

        testrunner = TestRunner(
            board=board,
            tests=tests,
            email_on_fail=settings.pop_optional(bool, 'email_on_fail', default=False),
            continue_on_fail=settings.pop_optional(bool,
                                                   'continue_on_fail', default=True)
        )

        controller = TestController(
            testrunner, log_func=log.info,
            verbose_log_func=log.notice,
            debug_log_func=log.debug,
            event_reporters=self.reporters
        )

        iterations = settings.pop_optional(int, 'iterations')
        if iterations:
            controller.run_condition = sc_run_n_iterations(ntimes=int(iterations))

        return controller

    def create_results_config(self, default_file: str) -> ResultsConfig:
        path = self.results_config.pop_optional(str, 'file', default=default_file)
        self.results_config.ensure_consumed()

        return ResultsConfig(path=path)

    @staticmethod
    def _generate_reporters(settings_config: Configuration,
                            reporter_types: List[Type[ReporterBase]]) -> List[ReporterBase]:
        reporters_config = settings_config.pop_optional(dict, 'reporters', {})
        valid_reporters = {t.configuration_key(): t for t in reporter_types}

        reporters = []
        for reporter_name, reporter_config in reporters_config.items():
            if reporter_name not in valid_reporters:
                raise TestsConfigError(
                    f'Found invalid reporter name "{reporter_name}". '
                    f'Valid reporter names are: {", ".join(valid_reporters.keys())}')
            reporter_type = valid_reporters[reporter_name]
            try:
                new_reporter = reporter_type.from_configuration(
                    Configuration(reporter_config)
                )
            except KeyError as key_error:
                raise TestsConfigError(
                    f'Error processing config for reporter "{reporter_type.display_name()}": '
                    f'Missing mandatory attribute {key_error}') from key_error
            except Exception as ex:
                raise TestsConfigError(
                    f'Error processing config for reporter "{reporter_type.display_name()}": {ex}'
                ) from ex
            else:
                reporters.append(new_reporter)
        return reporters

    def __populate_tests(self, tests_config: Configuration):
        self.tests = []

        sequence = tests_config.pop_optional(list, 'sequence', context='test config')
        if sequence:
            self.tests = self.tests_from_sequence(sequence, self.test_providers)

    def supported_actions(self, test_providers: List[TestsProvider] = None) -> dict:
        '''Return a map of supported action key strings, and corresponding providers'''
        if test_providers is None:
            test_providers = self.test_providers

        return TestsConfig._supported_actions(test_providers)

    @staticmethod
    def _supported_actions(test_providers: List[TestsProvider]) -> dict:
        '''Return a map of supported action key strings, and corresponding providers'''
        if test_providers is None:
            raise ValueError('None test_providers provided.')

        actions = {}
        for provider in test_providers:
            keys = provider.configuration_key()
            if isinstance(keys, str):
                keys = [keys]

            for key in keys:
                if key in actions:
                    raise TestsConfigError(
                        f'Error adding keys for provider {str(provider)}: key "{key}"'
                        f' is already registered by {str(actions[key])}')
                actions[key] = provider

        return actions

    @classmethod
    def tests_from_sequence(cls, sequence: list, test_providers: List[TestsProvider]) \
            -> List[TestDefinition]:
        '''Return a list of all tests generated by providers from a sequence'''
        if not isinstance(sequence, list):
            raise TestsConfigError(
                f'Invalid sequence, "sequence" must be a list (currently defined as {sequence})')

        all_tests = []
        supported_actions = cls._supported_actions(test_providers)

        # Parse sequence
        for action in sequence:
            if not isinstance(action, dict):
                raise TestsConfigError(
                    f'Invalid sequence action "{action}", which is not a dictionary')

            if len(action) != 1:
                raise TestsConfigError(
                    f'Sequence list elements must be single key elements, but got "{action}".'
                    f' Supported actions: {supported_actions.keys()}')

            action_key = next(iter(action))
            tests = cls.tests_from_action(action_key=action_key,
                                          action_config=action[action_key],
                                          supported_actions=supported_actions)
            all_tests.extend(tests)

        return all_tests

    @staticmethod
    def tests_from_action(action_key: str, action_config: Union[dict, Configuration],
                          supported_actions: dict) -> List[TestDefinition]:
        '''Return a list of all test definitions for a specific action and action providers'''
        provider = supported_actions.get(action_key)
        if not provider:
            raise TestsConfigError(
                f'No test provider was found for sequence action "{action_key}".'
                f' Supported actions: {supported_actions.keys()}')

        if isinstance(action_config, dict):
            tests = provider.all_tests(key=action_key, config=Configuration(action_config))
        else:
            tests = provider.all_tests(key=action_key, config=action_config)

        return tests

    def selected_tests(self) -> List[TestDefinition]:
        '''Return only selected tests among all tests available'''
        return list(filter(lambda test: (test.selected), self.tests))

    def print_tests(self, log_level: LogLevel = None, show_description: bool = False):
        TestsConfig.print_tests_definition(self.tests, log_level=log_level,
                                           show_description=show_description)

    @staticmethod
    def print_tests_definition(tests: List[TestDefinition], log_level: LogLevel = None,
                               show_description: bool = False):
        if log_level is None:
            log_level = LogLevel.INFO

        tests = sorted(
            tests, key=lambda test: test.provider.__class__.__name__)

        last_provider: Optional[TestsProvider] = None
        for test in tests:
            test_provider = cast(TestsProvider, test.provider)
            if test_provider != last_provider:
                if last_provider is not None:
                    log.log('', level=log_level)
                log.log(f'{test_provider.display_name()}:',
                        bold=True, level=log_level)
                last_provider = test_provider

            check = 'x' if test.selected else ' '
            log.log(f'[{check}] {test.name}',
                    indent=1, color='green' if test.selected else 'normal', level=log_level)

            if show_description:
                description = test.description
                if description is not None:
                    log.log(description, level=log_level, indent=2)
                else:
                    file, line = get_file_and_line(test.testclass)
                    file_loc_string = (f'{file}:{line or "unknown"}' if file is not None
                                       else 'unknown location')
                    log.log(f'No description - missing docstring at '
                            f'{file_loc_string} in {test.testclass.__name__}',
                            color='yellow', level=log_level, indent=2)

                if len(test.parameter_sets) and test.parameter_sets[0] is not None:
                    log.log('Parameters:', level=log_level, indent=2)
                    if len(test.parameter_sets) > 1:
                        serailized_parameters = yaml.safe_dump(test.parameter_sets)
                    else:
                        serailized_parameters = yaml.safe_dump(test.parameter_sets[0], indent=12)
                    log.log(serailized_parameters, level=log_level, indent=3)
                else:
                    log.log('', level=log_level)

        log.log('', level=log_level)

    @staticmethod
    def create_tests(tests: List[TestDefinition], board: Board) -> List[TestBase]:
        test_objects = []
        for test in tests:
            try:
                for parameters in test.parameter_sets:
                    parameters = parameters if parameters else dict()

                    if isinstance(parameters, dict):
                        test_object = test.testclass(board, **parameters)
                        test_object.settings = parameters
                    else:
                        test_object = test.testclass(board, parameters)
                        test_object.settings = {'default_setting': parameters}

                    test_objects.append(test_object)
            except Exception as e:
                if f'{e}'.startswith('__init__()'):
                    raise TestsConfigError(
                        f'The test "{test.name}" requires one or more parameters to be provided '
                        f'in the "parameters" attribute in your "pluma.yml" file:{os.linesep}'
                        f'    {e}')
                else:
                    raise TestsConfigError(
                        f'Failed to create test "{test.name}":{os.linesep}    {e}')

        return test_objects
