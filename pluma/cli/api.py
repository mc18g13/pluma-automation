from pluma.cli.resultsconfig import ResultsConfig
import sys
import time
import os
import json
from typing import List, Type

from pluma.core.baseclasses import Logger, LogLevel, ReporterBase
from pluma.core.builder import TestsBuildError,  YoctoCBuilder
from pluma.test import TestController
from pluma.cli import PlumaContext, PlumaConfig, TestsConfig, TargetConfig
from pluma.cli import PythonTestsProvider, ShellTestsProvider, CTestsProvider, \
    DeviceActionProvider
from pluma.reporting import XRayReporter
from pkg_resources import get_distribution

from .configpreprocessor import PlumaConfigPreprocessor

log = Logger()

START_TIMESTAMP = time.strftime('%Y%m%d-%H%M%S')


class Pluma:
    '''Top level API class for Pluma'''
    @staticmethod
    def tests_providers() -> list:
        return [PythonTestsProvider(), ShellTestsProvider(),
                CTestsProvider(), DeviceActionProvider()]

    @staticmethod
    def reporters() -> List[Type[ReporterBase]]:
        return [XRayReporter]

    @staticmethod
    def execute_run(tests_config_path: str, target_config_path: str,
                    check_only: bool = False) -> bool:
        '''Execute the "run" command, and allow checking only ("check" command).'''

        context = Pluma.create_target_context(target_config_path)
        tests_config = Pluma.create_tests_config(tests_config_path, context)
        results_config = Pluma.create_results_config(tests_config)

        controller = Pluma.build_test_controller(tests_config, context, show_tests_list=check_only)
        if check_only:
            log.log('Configuration and tests successfully validated.',
                    level=LogLevel.IMPORTANT)
            return True

        success = controller.run()
        if success:
            log.log('All tests were successful.',
                    level=LogLevel.IMPORTANT, color='green', bold=True)
        else:
            log.log('One of more test failed.',
                    level=LogLevel.IMPORTANT, color='red', bold=True)

        Pluma.save_results(controller, results_config)

        return success

    @staticmethod
    def execute_tests(tests_config_path: str, target_config_path: str):
        '''Execute the "tests" command, listing all tests.'''
        context = Pluma.create_target_context(target_config_path)
        tests_config = Pluma.create_tests_config(tests_config_path, context)

        log.log(
            'List of core and script tests available, based on the current configuration.')
        tests_config.print_tests(log_level=LogLevel.IMPORTANT, show_description=True)

    @staticmethod
    def execute_clean(force: bool = False):
        '''Execute the "clean" command.'''
        log.log('Removing log files...')
        try:
            logs_folder = os.path.dirname(
                os.path.abspath(sys.modules['__main__'].__file__))

            for file in os.listdir(logs_folder):
                if file.endswith('.log'):
                    os.remove(f'{logs_folder}/{file}')
        except Exception as e:
            raise TestsBuildError(
                f'Failed to remove log files: {e}')

        YoctoCBuilder.clean(force)

    @staticmethod
    def create_target_context(target_config_path: str) -> PlumaContext:
        env_vars = dict(os.environ)
        log.debug(f'Parsing target configuration "{target_config_path}"...')
        target_config = PlumaConfig.load_configuration('Target config', target_config_path,
                                                       PlumaConfigPreprocessor(env_vars))
        context = TargetConfig.create_context(target_config)

        for variable, env_value in ((var, val) for var, val in env_vars.items()
                                    if var in context.variables):
            log.warning([f'"{variable}" defined in both environment variables and target config.',
                         f'Using environment: {env_value}'])

        context.variables.update(env_vars)
        return context

    @staticmethod
    def create_tests_config(tests_config_path: str, context: PlumaContext) -> TestsConfig:
        log.debug(f'Parsing tests configuration "{tests_config_path}"...')
        tests_config = PlumaConfig.load_configuration('Tests config', tests_config_path,
                                                      PlumaConfigPreprocessor(context.variables))
        default_log = f'pluma-{START_TIMESTAMP}.log'
        context.board.log_file = tests_config.pop_optional(str, 'log', default_log)

        return TestsConfig(tests_config, Pluma.tests_providers(), reporters=Pluma.reporters())

    @staticmethod
    def create_results_config(tests_config: TestsConfig) -> ResultsConfig:
        return tests_config.create_results_config(default_file=f'pluma-results-{START_TIMESTAMP}.json')

    @staticmethod
    def build_test_controller(tests_config: TestsConfig, target_context: PlumaContext,
                              show_tests_list: bool) -> TestController:

        tests_list_log_level = LogLevel.INFO if show_tests_list else LogLevel.NOTICE
        tests_config.print_tests(log_level=tests_list_log_level)

        return tests_config.create_test_controller(target_context.board)

    @staticmethod
    def version() -> str:
        '''Return the version string of Pluma'''
        top_level_package = __package__.split('.')[0]
        return get_distribution(top_level_package).version

    @staticmethod
    def save_results(controller: TestController, results_config: ResultsConfig):
        settings_summary = controller.collect_test_settings()
        data_summary = controller.get_test_data_summary()
        results = {
            'data': data_summary,
            'settings': settings_summary,
            'results': controller.results
        }

        with open(results_config.path, 'w') as f:
            json.dump(results, f, indent=4)
