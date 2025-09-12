# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import concurrent.futures
import logging
import os
import sys
import threading
import time
from typing import Optional

import yaml
from pydantic import BaseModel
from rich.progress import Progress

from agenteval import defaults
from agenteval.evaluators import EvaluatorFactory
from agenteval.plan.exceptions import TestFailureError
from agenteval.plan.logging import log_run_end, log_run_start
from agenteval.summary import create_markdown_summary
from agenteval.targets import TargetFactory
from agenteval.test import TestSuite

_DEFAULT_PLAN_FILE_NAME = "agenteval.yml"

_DEFAULT__PLAN = {
    "evaluator": {"model": "claude-3", "eval_method": "canonical"},
    "target": {
        "type": "bedrock-agent",
        "bedrock_agent_id": None,
        "bedrock_agent_alias_id": None,
    },
    "tests": {
        "retrieve_missing_documents": {
            "steps": ["Ask agent for a list of missing documents for claim-006."],
            "expected_results": ["The agent returns a list of missing documents."],
        }
    },
}


sys.path.append(".")
logger = logging.getLogger(__name__)


class Plan(BaseModel):
    """Encapsulates the configurations for a test plan, which includes information
    about the evaluator, the target, the tests to be executed, and various settings
    for running the tests.

    Attributes:
        config: A dictionary containing the test plan configurations.
    """

    config: dict

    @classmethod
    def load(
        cls,
        plan_dir: Optional[str] = None,
        plan_file_name: Optional[str] = _DEFAULT_PLAN_FILE_NAME,
    ) -> Plan:
        """Loads the test plan configurations from YAML.

        Args:
            plan_dir (Optional[str]): The directory containing the test plan.
                If `None`, the current working directory will be used.
                plan_file_name (Optional[str]): The name of the file that contains the plan YAML spec
        Returns:
            Plan: A `Plan` instance containing the loaded test plan configurations.
        """
        plan_path = os.path.join(plan_dir or os.getcwd(), plan_file_name)
        plan = cls._load_yaml(plan_path)
        return cls(config=plan)

    @staticmethod
    def _load_yaml(path: str) -> dict:
        with open(path) as stream:
            return yaml.safe_load(stream)

    @staticmethod
    def init_plan(
        plan_dir: Optional[str] = None,
        plan_file_name: Optional[str] = _DEFAULT_PLAN_FILE_NAME,
    ) -> str:
        """Initializes a new test plan configuration YAML file.

        Args:
            plan_dir (Optional[str]): The directory where the YAML file will be stored.
                If `None`, the current working directory will be used.
            plan_file_name (Optional[str]): The name of the file that contains the plan YAML spec
        Returns:
            str: The path to the YAML file.
        """
        plan_path = os.path.join(plan_dir or os.getcwd(), plan_file_name)

        # check if plan exists
        if os.path.exists(plan_path):
            logger.error(f"[red]Test plan already exists at {plan_path}")

            raise FileExistsError

        with open(plan_path, "w") as stream:
            yaml.safe_dump(_DEFAULT__PLAN, stream, sort_keys=False)

        logger.info(f"[green]Test plan created at {plan_path}")

        return plan_path

    def _resolve_num_threads(self, num_tests: int, num_threads: Optional[int]) -> int:
        # Check if target requires sequential execution
        target_type = self.config.get("target", {}).get("type")
        if target_type == "weni":
            logger.info("Weni target detected - forcing single-threaded execution for WebSocket stability")
            return 1

        return (
            min(num_tests, defaults.MAX_NUM_THREADS)
            if num_threads is None
            else num_threads
        )

    def run(
        self,
        verbose: bool = False,
        num_threads: Optional[int] = None,
        work_dir: Optional[str] = None,
        filter: Optional[str] = None,
        watch: bool = False,
    ):
        """Run the test plan.

        Args:
            verbose (bool): Whether to enable verbose logging.
            num_threads (Optional[int]): Number of threads used to run tests concurrently.
                If `None`, the thread count will be set to the number of tests (up to a maximum of `45` threads).
            work_dir (Optional[str]): The directory where the test result and trace will be
                generated. If `None`, the assets will be saved to the current working directory.
            filter (Optional[str]): Specifies the test(s) to run, where multiple tests should be seperated using a comma.
                If `None`, all tests will be run.
        """
        self._setup_run(filter, work_dir, num_threads, watch)

        log_run_start(verbose, self._num_tests, self._num_threads)

        start = time.time()

        if watch:
            self._run_watch_mode()
        else:
            with Progress(transient=True) as self._progress:
                self._tracker = self._progress.add_task("running...", total=self._num_tests)
                self._run_concurrent()

        fail_count = self._num_tests - self._pass_count

        log_run_end(
            verbose,
            self._results,
            self._num_tests,
            self._pass_count,
            fail_count,
            round(time.time() - start, 2),
            sum(self._evaluator_input_token_counts),
            sum(self._evaluator_output_token_counts),
        )

        create_markdown_summary(
            self._work_dir,
            self._pass_count,
            self._num_tests,
            self._test_suite.tests,
            list(self._results.values()),
        )

        if fail_count:
            raise TestFailureError

    def _setup_run(
        self, filter: Optional[str], work_dir: Optional[str], num_threads: Optional[int], watch: bool = False
    ):
        self._evaluator_factory = EvaluatorFactory(config=self.config["evaluator"])
        self._target_factory = TargetFactory(config=self.config["target"])
        self._test_suite = TestSuite.load(self.config["tests"], filter)
        self._lock = threading.Lock()
        self._num_tests = self._test_suite.num_tests
        self._work_dir = work_dir or os.getcwd()
        # In watch mode, force single-threaded execution for readable output
        self._num_threads = 1 if watch else self._resolve_num_threads(self._num_tests, num_threads)
        self._results = {test.name: None for test in self._test_suite}
        self._evaluator_input_token_counts = []
        self._evaluator_output_token_counts = []
        self._pass_count = 0
        self._watch_mode = watch

    def _run_concurrent(self):
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._num_threads
        ) as executor:
            futures = [
                executor.submit(self._run_test, test) for test in self._test_suite
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    raise e

    def _run_watch_mode(self):
        """Run tests in watch mode with real-time conversation display."""
        import click
        
        click.echo("\n" + "="*80)
        click.echo(f"🔍 WATCH MODE: Running {self._num_tests} test(s) sequentially")
        click.echo("="*80 + "\n")
        
        for i, test in enumerate(self._test_suite, 1):
            click.echo(f"📋 Test {i}/{self._num_tests}: {test.name}")
            click.echo("-" * 60)
            
            # Create a custom evaluator that reports conversations in real-time
            target = self._target_factory.create()
            evaluator = self._evaluator_factory.create(
                test=test,
                target=target,
                work_dir=self._work_dir,
            )
            
            # Monkey patch the evaluator to show conversations in real-time
            original_add_turn = evaluator.conversation.add_turn
            original_invoke_target = evaluator._invoke_target
            
            def watch_invoke_target(user_input: str):
                # Show user prompt immediately when sent
                click.echo(f"\n👤 USER: {user_input}")
                click.echo("🤖 AGENT: ", nl=False)  # Print "AGENT: " without newline, waiting for response
                
                # Call the original method to get agent response
                agent_response = original_invoke_target(user_input)
                
                # Show the agent response
                click.echo(agent_response)
                click.echo()  # Add blank line for readability
                
                return agent_response
            
            def watch_add_turn(user_message: str, agent_response: str):
                # Call the original method (conversation display already handled in watch_invoke_target)
                original_add_turn(user_message, agent_response)
            
            # Apply the patches
            evaluator._invoke_target = watch_invoke_target
            evaluator.conversation.add_turn = watch_add_turn
            
            # Run the test
            result = evaluator.run()
            
            # Display test result
            if result.passed:
                click.echo(f"✅ PASSED: {test.name}")
                click.echo(f"   Result: {result.result}")
                if result.reasoning:
                    click.echo(f"   Reasoning: {result.reasoning}")
            else:
                click.echo(f"❌ FAILED: {test.name}")
                click.echo(f"   Result: {result.result}")
                if result.reasoning:
                    click.echo(f"   Reasoning: {result.reasoning}")
            
            # Update results
            with self._lock:
                if result.passed is True:
                    self._pass_count += 1
                self._results[test.name] = result
                self._evaluator_input_token_counts.append(evaluator.input_token_count)
                self._evaluator_output_token_counts.append(evaluator.output_token_count)
            
            if i < self._num_tests:
                click.echo("\n" + "="*80 + "\n")
        
        click.echo("\n" + "="*80)
        click.echo(f"🏁 WATCH MODE COMPLETED: {self._pass_count}/{self._num_tests} tests passed")
        click.echo("="*80 + "\n")

    def _run_test(self, test):
        target = self._target_factory.create()
        evaluator = self._evaluator_factory.create(
            test=test,
            target=target,
            work_dir=self._work_dir,
        )

        result = evaluator.run()

        with self._lock:
            if result.passed is True:
                self._pass_count += 1
            self._results[test.name] = result
            self._evaluator_input_token_counts.append(evaluator.input_token_count)
            self._evaluator_output_token_counts.append(evaluator.output_token_count)
            self._progress.update(self._tracker, advance=1)
