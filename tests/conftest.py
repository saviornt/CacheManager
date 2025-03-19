import pytest
import datetime
from pathlib import Path

# Create a directory for test results if it doesn't exist
results_dir = Path("tests/test_results")
results_dir.mkdir(exist_ok=True)


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Set up the results file when pytest is configured."""
    result_file = results_dir / f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    # Store the result file path for later use
    config.result_file = result_file
    with open(result_file, "w") as f:
        f.write(f"Test Run: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report):
    """Process the test report for each phase (setup, call, teardown)."""
    if report.when == "call":  # Only record the actual test phase, not setup/teardown
        # Get the path from config via the request fixture
        config = getattr(report, "_config", None)
        if config is None:
            return
            
        result_file = getattr(config, "result_file", None)
        
        if result_file:
            outcome = "PASSED" if report.passed else "FAILED"
            with open(result_file, "a") as f:
                f.write(f"Test: {report.nodeid}\n")
                f.write(f"Outcome: {outcome}\n")
                if report.longrepr:
                    f.write(f"Details:\n{report.longrepr}\n")
                f.write("-" * 80 + "\n\n")


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add a summary of the test run to the results file."""
    result_file = getattr(config, "result_file", None)
    
    if result_file:
        passed_count = len(terminalreporter.stats.get('passed', []))
        failed_count = len(terminalreporter.stats.get('failed', []))
        total_count = passed_count + failed_count
        
        with open(result_file, "a") as f:
            f.write("\nSummary:\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total tests: {total_count}\n")
            f.write(f"Passed: {passed_count}\n")
            f.write(f"Failed: {failed_count}\n")
            f.write(f"Exit code: {exitstatus}\n")
            f.write("=" * 80 + "\n")
        
        print(f"\nTest results saved to: {result_file}") 