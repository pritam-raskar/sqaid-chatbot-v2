#!/usr/bin/env python3
"""
Simple test runner for chatbot system
Usage: python run_tests.py [--coverage] [--verbose] [--markers MARKERS]
"""
import sys
import subprocess
from pathlib import Path


def run_tests(coverage=False, verbose=False, markers=None, html_report=False):
    """Run pytest with specified options"""
    cmd = ["pytest"]

    if markers:
        cmd.extend(["-m", markers])

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=app", "--cov-report=term-missing"])
        if html_report:
            cmd.append("--cov-report=html")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run chatbot tests")
    parser.add_argument("-c", "--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-m", "--markers", help="Run specific markers (unit, integration, e2e)")
    parser.add_argument("-r", "--html-report", action="store_true", help="Generate HTML coverage report")

    args = parser.parse_args()

    exit_code = run_tests(
        coverage=args.coverage,
        verbose=args.verbose,
        markers=args.markers,
        html_report=args.html_report
    )

    sys.exit(exit_code)
