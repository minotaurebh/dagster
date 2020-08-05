from __future__ import print_function

import os
import re

import pytest
from click import UsageError
from click.testing import CliRunner

from dagster import seven
from dagster.cli.pipeline import execute_list_command, pipeline_list_command
from dagster.core.instance import DagsterInstance
from dagster.core.test_utils import mocked_instance
from dagster.grpc.server import GrpcServerProcess
from dagster.grpc.types import LoadableTargetOrigin
from dagster.utils import file_relative_path

from .test_cli_commands import managed_grpc_instance


def no_print(_):
    return None


def assert_correct_bar_repository_output(result):
    assert result.exit_code == 0
    assert result.output == (
        'Repository bar\n'
        '**************\n'
        'Pipeline: baz\n'
        'Description:\n'
        'Not much tbh\n'
        'Solids: (Execution Order)\n'
        '    do_input\n'
        '*************\n'
        'Pipeline: foo\n'
        'Solids: (Execution Order)\n'
        '    do_something\n'
        '    do_input\n'
    )


def assert_correct_extra_repository_output(result):
    assert result.exit_code == 0
    assert result.output == (
        'Repository extra\n'
        '****************\n'
        'Pipeline: extra\n'
        'Solids: (Execution Order)\n'
        '    do_something\n'
    )


@pytest.mark.skipif(seven.IS_WINDOWS, reason="no named sockets on Windows")
def test_list_command_grpc_socket():
    runner = CliRunner()

    with GrpcServerProcess(
        loadable_target_origin=LoadableTargetOrigin(
            python_file=file_relative_path(__file__, 'test_cli_commands.py'), attribute='bar'
        ),
    ).create_ephemeral_client() as api_client:
        execute_list_command(
            {'grpc_socket': api_client.socket}, no_print, DagsterInstance.local_temp(),
        )
        execute_list_command(
            {'grpc_socket': api_client.socket, 'grpc_host': api_client.host},
            no_print,
            DagsterInstance.local_temp(),
        )

        result = runner.invoke(pipeline_list_command, ['--grpc_socket', api_client.socket])
        assert_correct_bar_repository_output(result)

        result = runner.invoke(
            pipeline_list_command,
            ['--grpc_socket', api_client.socket, '--grpc_host', api_client.host],
        )
        assert_correct_bar_repository_output(result)


def test_list_command_cli():
    runner = CliRunner()

    result = runner.invoke(
        pipeline_list_command,
        ['-f', file_relative_path(__file__, 'test_cli_commands.py'), '-a', 'bar'],
    )
    assert_correct_bar_repository_output(result)

    result = runner.invoke(
        pipeline_list_command,
        [
            '-f',
            file_relative_path(__file__, 'test_cli_commands.py'),
            '-a',
            'bar',
            '-d',
            os.path.dirname(__file__),
        ],
    )
    assert_correct_bar_repository_output(result)

    with GrpcServerProcess(
        loadable_target_origin=LoadableTargetOrigin(
            python_file=file_relative_path(__file__, 'test_cli_commands.py'), attribute='bar'
        ),
        force_port=True,
    ).create_ephemeral_client() as api_client:

        result = runner.invoke(pipeline_list_command, ['--grpc_port', api_client.port])
        assert_correct_bar_repository_output(result)

        result = runner.invoke(
            pipeline_list_command, ['--grpc_port', api_client.port, '--grpc_host', api_client.host],
        )
        assert_correct_bar_repository_output(result)

        result = runner.invoke(pipeline_list_command, ['--grpc_port', api_client.port])
        assert_correct_bar_repository_output(result)

        result = runner.invoke(
            pipeline_list_command,
            ['--grpc_port', api_client.port, '--grpc_socket', 'foonamedsocket'],
        )
        assert result.exit_code != 0

    result = runner.invoke(
        pipeline_list_command,
        ['-m', 'dagster_tests.cli_tests.command_tests.test_cli_commands', '-a', 'bar'],
    )
    assert_correct_bar_repository_output(result)

    with pytest.warns(
        UserWarning,
        match=re.escape(
            'You are using the legacy repository yaml format. Please update your file '
        ),
    ):
        result = runner.invoke(
            pipeline_list_command, ['-w', file_relative_path(__file__, 'repository_module.yaml')]
        )
        assert_correct_bar_repository_output(result)

    result = runner.invoke(
        pipeline_list_command, ['-w', file_relative_path(__file__, 'workspace.yaml')]
    )
    assert_correct_bar_repository_output(result)

    result = runner.invoke(
        pipeline_list_command,
        [
            '-w',
            file_relative_path(__file__, 'workspace.yaml'),
            '-w',
            file_relative_path(__file__, 'override.yaml'),
        ],
    )
    assert_correct_extra_repository_output(result)

    result = runner.invoke(
        pipeline_list_command,
        [
            '-f',
            'foo.py',
            '-m',
            'dagster_tests.cli_tests.command_tests.test_cli_commands',
            '-a',
            'bar',
        ],
    )
    assert result.exit_code == 2

    result = runner.invoke(
        pipeline_list_command, ['-m', 'dagster_tests.cli_tests.command_tests.test_cli_commands'],
    )
    assert_correct_bar_repository_output(result)

    result = runner.invoke(
        pipeline_list_command, ['-f', file_relative_path(__file__, 'test_cli_commands.py')]
    )
    assert_correct_bar_repository_output(result)


@pytest.mark.parametrize('gen_instance', [mocked_instance(), managed_grpc_instance()])
def test_list_command(gen_instance):
    with gen_instance as instance:
        execute_list_command(
            {
                'repository_yaml': None,
                'python_file': file_relative_path(__file__, 'test_cli_commands.py'),
                'module_name': None,
                'fn_name': 'bar',
            },
            no_print,
            instance,
        )

        execute_list_command(
            {
                'repository_yaml': None,
                'python_file': file_relative_path(__file__, 'test_cli_commands.py'),
                'module_name': None,
                'fn_name': 'bar',
                'working_directory': os.path.dirname(__file__),
            },
            no_print,
            instance,
        )

        with GrpcServerProcess(
            loadable_target_origin=LoadableTargetOrigin(
                python_file=file_relative_path(__file__, 'test_cli_commands.py'), attribute='bar'
            ),
            force_port=True,
        ).create_ephemeral_client() as api_client:
            execute_list_command(
                {'grpc_port': api_client.port}, no_print, instance,
            )

            # Can't supply both port and socket
            with pytest.raises(UsageError):
                execute_list_command(
                    {'grpc_port': api_client.port, 'grpc_socket': 'foonamedsocket'},
                    no_print,
                    instance,
                )

        execute_list_command(
            {
                'repository_yaml': None,
                'python_file': None,
                'module_name': 'dagster_tests.cli_tests.command_tests.test_cli_commands',
                'fn_name': 'bar',
            },
            no_print,
            instance,
        )

        with pytest.warns(
            UserWarning,
            match=re.escape(
                'You have used -y or --repository-yaml to load a workspace. This is deprecated and '
                'will be eliminated in 0.9.0.'
            ),
        ):
            execute_list_command(
                {
                    'repository_yaml': file_relative_path(__file__, 'repository_module.yaml'),
                    'python_file': None,
                    'module_name': None,
                    'fn_name': None,
                },
                no_print,
                instance,
            )

        with pytest.raises(UsageError):
            execute_list_command(
                {
                    'repository_yaml': None,
                    'python_file': 'foo.py',
                    'module_name': 'dagster_tests.cli_tests.command_tests.test_cli_commands',
                    'fn_name': 'bar',
                },
                no_print,
                instance,
            )