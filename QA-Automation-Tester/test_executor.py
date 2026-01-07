#!/usr/bin/env python3
"""
Test Executor Script

Runs all test files matching *.test.py pattern in parallel.
Supports both file and directory arguments.

Usage:
    python test_executor.py path/to/test_file.test.py
    python test_executor.py path/to/test_directory/
    python test_executor.py .  # Current directory
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import json


class TestResult:
    """Represents the result of a single test file execution."""
    
    def __init__(self, test_file: Path, success: bool, exit_code: int = 0, 
                 stdout: str = "", stderr: str = "", execution_time: float = 0.0):
        self.test_file = test_file
        self.success = success
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time = execution_time
        self.error_summary = self._extract_error_summary()
    
    def _extract_error_summary(self) -> str:
        """Extract a concise error summary from stderr."""
        if not self.stderr:
            return ""
        
        lines = self.stderr.strip().split('\n')
        # Get last few lines that might contain error info
        error_lines = [line for line in lines[-10:] if line.strip()]
        return '\n'.join(error_lines[-5:])  # Last 5 non-empty lines


async def run_test_file(test_file: Path, timeout: Optional[int] = None) -> TestResult:
    """
    Run a single test file and return the result.
    Each test file runs exactly once - no retries or reruns.
    
    Args:
        test_file: Path to the test file
        timeout: Optional timeout in seconds
        
    Returns:
        TestResult object with execution details
    """
    start_time = datetime.now()
    
    try:
        # Run the test file using Python - execute once, no retries
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(test_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=test_file.parent
        )
        
        # Wait for completion with optional timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            return TestResult(
                test_file=test_file,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Test execution timed out after {timeout} seconds",
                execution_time=execution_time
            )
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Decode output
        stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ""
        stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""
        
        # Determine success (exit code 0 = success)
        success = process.returncode == 0
        
        return TestResult(
            test_file=test_file,
            success=success,
            exit_code=process.returncode or 0,
            stdout=stdout_text,
            stderr=stderr_text,
            execution_time=execution_time
        )
        
    except Exception as e:
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        return TestResult(
            test_file=test_file,
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Failed to execute test: {str(e)}",
            execution_time=execution_time
        )


def find_test_files(path: Path) -> List[Path]:
    """
    Find all test files matching *.test.py pattern.
    
    Args:
        path: File or directory path
        
    Returns:
        List of test file paths
    """
    test_files = []
    
    if path.is_file():
        # Single file provided
        if path.name.endswith('.test.py'):
            test_files.append(path)
        else:
            print(f"Warning: {path} does not match *.test.py pattern", file=sys.stderr)
    elif path.is_dir():
        # Directory provided - find all *.test.py files recursively
        test_files = list(path.rglob('*.test.py'))
        test_files.sort()  # Sort for consistent ordering
    else:
        print(f"Error: {path} is not a valid file or directory", file=sys.stderr)
    
    return test_files


async def run_tests_parallel(test_files: List[Path], max_concurrent: int = 5, 
                            timeout: Optional[int] = None) -> List[TestResult]:
    """
    Run multiple test files in parallel.
    
    Args:
        test_files: List of test file paths
        max_concurrent: Maximum number of tests to run concurrently
        timeout: Optional timeout per test in seconds
        
    Returns:
        List of TestResult objects
    """
    if not test_files:
        return []
    
    # Track which tests are running to prevent duplicates
    running_tests = set()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_semaphore(test_file: Path) -> TestResult:
        # Ensure each test file runs only once
        test_key = str(test_file.resolve())
        if test_key in running_tests:
            print(f"⚠️  Skipping duplicate: {test_file.name} (already running)")
            return TestResult(
                test_file=test_file,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Test was skipped - duplicate detected",
                execution_time=0.0
            )
        
        running_tests.add(test_key)
        try:
            async with semaphore:
                print(f"Running: {test_file.name}")
                result = await run_test_file(test_file, timeout=timeout)
                status = "✅ PASS" if result.success else "❌ FAIL"
                print(f"{status}: {test_file.name} ({result.execution_time:.2f}s)")
                return result
        finally:
            # Remove from running set after completion
            running_tests.discard(test_key)
    
    # Run all tests in parallel - each test file will run exactly once
    results = await asyncio.gather(*[run_with_semaphore(tf) for tf in test_files])
    return results


def generate_summary_report(results: List[TestResult]) -> str:
    """
    Generate a summary report of test results.
    
    Args:
        results: List of TestResult objects
        
    Returns:
        Formatted summary report string
    """
    if not results:
        return "No tests were executed."
    
    total_tests = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total_tests - passed
    total_time = sum(r.execution_time for r in results)
    
    report_lines = [
        "=" * 80,
        "TEST EXECUTION SUMMARY",
        "=" * 80,
        f"Total Tests: {total_tests}",
        f"Passed: {passed}",
        f"Failed: {failed}",
        f"Success Rate: {(passed/total_tests)*100:.1f}%",
        f"Total Execution Time: {total_time:.2f}s",
        "=" * 80,
        ""
    ]
    
    # List passed tests
    if passed > 0:
        report_lines.append("PASSED TESTS:")
        report_lines.append("-" * 80)
        for result in results:
            if result.success:
                report_lines.append(f"  ✅ {result.test_file.name} ({result.execution_time:.2f}s)")
        report_lines.append("")
    
    # List failed tests with error details
    if failed > 0:
        report_lines.append("FAILED TESTS:")
        report_lines.append("-" * 80)
        for result in results:
            if not result.success:
                report_lines.append(f"  ❌ {result.test_file.name} (Exit Code: {result.exit_code}, Time: {result.execution_time:.2f}s)")
                report_lines.append(f"      File: {result.test_file}")
                
                # Add error summary
                if result.error_summary:
                    report_lines.append("      Error Summary:")
                    for line in result.error_summary.split('\n'):
                        if line.strip():
                            report_lines.append(f"        {line}")
                
                # Add stderr if available
                if result.stderr and result.stderr.strip():
                    stderr_lines = result.stderr.strip().split('\n')
                    # Limit to last 20 lines to avoid overwhelming output
                    if len(stderr_lines) > 20:
                        report_lines.append("      Last 20 lines of stderr:")
                        for line in stderr_lines[-20:]:
                            report_lines.append(f"        {line}")
                    else:
                        report_lines.append("      stderr:")
                        for line in stderr_lines:
                            report_lines.append(f"        {line}")
                
                report_lines.append("")
    
    report_lines.append("=" * 80)
    
    return '\n'.join(report_lines)


def save_detailed_log(results: List[TestResult], log_file: Path) -> None:
    """
    Save detailed test execution logs to a file.
    
    Args:
        results: List of TestResult objects
        log_file: Path to save the log file
    """
    log_lines = [
        f"Test Execution Log",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 80,
        ""
    ]
    
    # Add summary
    total_tests = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total_tests - passed
    
    log_lines.extend([
        "SUMMARY",
        "-" * 80,
        f"Total Tests: {total_tests}",
        f"Passed: {passed}",
        f"Failed: {failed}",
        f"Success Rate: {(passed/total_tests)*100:.1f}%",
        "",
        "=" * 80,
        ""
    ])
    
    # Add detailed results for each test
    for i, result in enumerate(results, 1):
        log_lines.extend([
            f"TEST {i}/{total_tests}: {result.test_file.name}",
            "-" * 80,
            f"File: {result.test_file}",
            f"Status: {'PASS' if result.success else 'FAIL'}",
            f"Exit Code: {result.exit_code}",
            f"Execution Time: {result.execution_time:.2f}s",
            ""
        ])
        
        if result.stdout:
            log_lines.extend([
                "STDOUT:",
                "-" * 40,
                result.stdout,
                ""
            ])
        
        if result.stderr:
            log_lines.extend([
                "STDERR:",
                "-" * 40,
                result.stderr,
                ""
            ])
        
        log_lines.append("=" * 80)
        log_lines.append("")
    
    # Write to file
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
    
    print(f"Detailed log saved to: {log_file}")


async def main():
    """Main entry point for the test executor."""
    parser = argparse.ArgumentParser(
        description="Run test files matching *.test.py pattern in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_executor.py test_file.test.py
  python test_executor.py tests/
  python test_executor.py . --max-concurrent 10
  python test_executor.py tests/ --timeout 300 --log-file custom.log
        """
    )
    
    parser.add_argument(
        'path',
        type=str,
        help='Path to test file or directory containing *.test.py files'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=5,
        help='Maximum number of tests to run concurrently (default: 5)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='Timeout per test in seconds (default: no timeout)'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='Path to save detailed log file (default: test_results_TIMESTAMP.log)'
    )
    parser.add_argument(
        '--no-summary',
        action='store_true',
        help='Do not print summary to console (only save to log file)'
    )
    
    args = parser.parse_args()
    
    # Resolve the input path
    input_path = Path(args.path).resolve()
    
    if not input_path.exists():
        print(f"Error: Path does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Find test files
    print(f"Searching for test files in: {input_path}")
    test_files = find_test_files(input_path)
    
    if not test_files:
        print(f"No test files (*.test.py) found in {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Deduplicate test files to ensure each test runs only once
    # Use a dict to preserve order while removing duplicates
    seen = {}
    for tf in test_files:
        # Use absolute path as key to catch duplicates
        key = str(tf.resolve())
        if key not in seen:
            seen[key] = tf
    
    test_files = list(seen.values())
    
    print(f"Found {len(test_files)} test file(s) (after deduplication):")
    for tf in test_files:
        print(f"  - {tf}")
    print()
    
    # Run tests in parallel
    print(f"Running {len(test_files)} test(s) with max {args.max_concurrent} concurrent...")
    print("-" * 80)
    
    start_time = datetime.now()
    results = await run_tests_parallel(
        test_files,
        max_concurrent=args.max_concurrent,
        timeout=args.timeout
    )
    end_time = datetime.now()
    total_execution_time = (end_time - start_time).total_seconds()
    
    print("-" * 80)
    print()
    
    # Generate summary
    summary = generate_summary_report(results)
    
    # Print summary unless --no-summary is set
    if not args.no_summary:
        print(summary)
    
    # Determine log file path
    if args.log_file:
        log_file = Path(args.log_file)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = Path(f"test_results_{timestamp}.log")
    
    # Save detailed log
    save_detailed_log(results, log_file)
    
    # Exit with appropriate code
    failed_count = sum(1 for r in results if not r.success)
    if failed_count > 0:
        print(f"\n⚠️  {failed_count} test(s) failed. See {log_file} for details.")
        sys.exit(1)
    else:
        print(f"\n✅ All tests passed! See {log_file} for details.")
        sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())

