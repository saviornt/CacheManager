import pytest
import datetime
import platform
import sys
import time
import os
import socket
from pathlib import Path
from typing import Dict, List, Set, Any

# Create a directory for test results if it doesn't exist
results_dir = Path("tests/results")
results_dir.mkdir(exist_ok=True)

# Dictionary to track test start times
test_start_times: Dict[str, float] = {}
# Dictionary to track module-specific result files
module_result_files: Dict[str, Path] = {}
# Track which modules we've seen
processed_modules: Set[str] = set()

@pytest.hookimpl(trylast=True)
def pytest_configure(config: Any) -> None:
    """Set up the global session timestamp and prepare for per-module logging."""
    # Get the test session information - use a single timestamp for the entire run
    config.session_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Store the session start time for duration measurement
    config._start_time = time.time()
    
    # Initialize the collection for module files
    config.module_result_files = {}

@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session: Any, config: Any, items: List[Any]) -> None:
    """Group collected test items by module and prepare log files for each module."""
    global processed_modules
    processed_modules = set()
    
    # Group tests by module
    modules_to_tests = {}
    for item in items:
        module_path = item.nodeid.split("::")[0]
        module_name = os.path.basename(module_path).replace(".py", "")
        
        if module_name not in modules_to_tests:
            modules_to_tests[module_name] = []
        modules_to_tests[module_name].append(item.nodeid)
    
    # Create a result file for each module
    timestamp = config.session_timestamp
    for module_name, tests in modules_to_tests.items():
        result_file = results_dir / f"{module_name}_results_{timestamp}.log"
        config.module_result_files[module_name] = result_file
        
        with open(result_file, "w") as f:
            f.write(f"Test Run: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Module: {module_name}\n")
            f.write("=" * 80 + "\n\n")
            
            # Add system information
            f.write("System Information:\n")
            f.write("-" * 80 + "\n")
            f.write(f"Python version: {sys.version}\n")
            f.write(f"Platform: {platform.platform()}\n")
            f.write(f"Machine: {platform.machine()}\n")
            f.write(f"Hostname: {socket.gethostname()}\n")
            f.write(f"Processor: {platform.processor()}\n")
            f.write(f"Number of CPUs: {os.cpu_count()}\n")
            f.write(f"Working directory: {os.getcwd()}\n")
            f.write(f"Pytest version: {pytest.__version__}\n")
            f.write("-" * 80 + "\n\n")
            
            # List the collected tests for this module
            f.write(f"Collected Tests for {module_name}: {len(tests)}\n")
            for idx, test in enumerate(tests, 1):
                f.write(f"{idx}. {test}\n")
            f.write("\n" + "=" * 80 + "\n\n")

def _get_module_file(nodeid: str, config: Any) -> Path:
    """Helper function to get the module-specific result file."""
    module_path = nodeid.split("::")[0]
    module_name = os.path.basename(module_path).replace(".py", "")
    return config.module_result_files.get(module_name)

@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item: Any) -> None:
    """Record the start time of each test."""
    global processed_modules
    
    # Track when the test starts
    test_start_times[item.nodeid] = time.time()
    
    # Get module name
    module_path = item.nodeid.split("::")[0]
    module_name = os.path.basename(module_path).replace(".py", "")
    
    # If we haven't processed this module yet, add a header
    if module_name not in processed_modules:
        processed_modules.add(module_name)
        
        # Get the result file for this module
        result_file = _get_module_file(item.nodeid, item.config)
        if result_file:
            with open(result_file, "a") as f:
                f.write(f"Running Tests:\n")
                f.write("-" * 80 + "\n\n")

@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: Any) -> None:
    """Process the test report for each phase and log to the module-specific file."""
    if report.when == "call":  # Only record the actual test phase, not setup/teardown
        # Get the config
        config = getattr(report, "_config", None)
        if config is None:
            return
            
        # Get the module-specific result file
        result_file = _get_module_file(report.nodeid, config)
        
        if result_file:
            # Calculate test duration
            test_duration = time.time() - test_start_times.get(report.nodeid, time.time())
            outcome = "PASSED" if report.passed else "FAILED"
            
            # Get test info directly from the item
            with open(result_file, "a") as f:
                # Basic test information
                test_name = report.nodeid.split("::")[-1]
                f.write(f"Test: {test_name}\n")
                f.write(f"Outcome: {outcome}\n")
                f.write(f"Duration: {test_duration:.4f}s\n")
                
                # Extract docstring and metadata
                if hasattr(report, "keywords"):
                    docstring = report.keywords.get("__doc__", "No docstring available")
                    f.write(f"Description: {docstring}\n")
                
                # Get test markers
                markers = getattr(report, "own_markers", [])
                if markers:
                    marker_str = ", ".join([m.name for m in markers])
                    f.write(f"Markers: {marker_str}\n")
                
                # Get test parameters if parametrized
                if hasattr(report, "keywords") and "parametrize" in report.keywords:
                    params = getattr(report, "callspec", None)
                    if params and hasattr(params, "params"):
                        f.write("Parameters:\n")
                        for name, value in params.params.items():
                            f.write(f"  {name}: {value}\n")
                
                # Test details (for failed tests, this includes the traceback)
                if report.longrepr:
                    f.write(f"Details:\n{report.longrepr}\n")
                
                # For passed tests, include any captured output if available
                elif report.passed and hasattr(report, "capstdout") and report.capstdout:
                    f.write("Captured stdout:\n")
                    f.write(report.capstdout)
                
                # Include any warnings
                if hasattr(report, "warnings") and report.warnings:
                    f.write("Warnings:\n")
                    for warning in report.warnings:
                        f.write(f"  {warning.message}\n")
                
                f.write("-" * 80 + "\n\n")

@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """Add a detailed summary to each module's log file and print overall results."""
    # Get stats for each module
    stats = terminalreporter.stats
    module_stats = {}
    
    # Process stats by module
    for outcome in ['passed', 'failed', 'skipped', 'error', 'xfailed', 'xpassed']:
        for report in stats.get(outcome, []):
            module_path = report.nodeid.split("::")[0]
            module_name = os.path.basename(module_path).replace(".py", "")
            
            if module_name not in module_stats:
                module_stats[module_name] = {
                    'passed': 0, 'failed': 0, 'skipped': 0,
                    'error': 0, 'xfailed': 0, 'xpassed': 0,
                    'total': 0
                }
            
            module_stats[module_name][outcome] += 1
            module_stats[module_name]['total'] += 1
    
    # Write summary for each module
    run_duration = time.time() - getattr(config, "_start_time", time.time())
    result_files = []
    
    for module_name, module_file in config.module_result_files.items():
        if module_name in module_stats:
            stats_data = module_stats[module_name]
            
            with open(module_file, "a") as f:
                f.write("\nTest Run Summary:\n")
                f.write("=" * 80 + "\n")
                f.write(f"Module: {module_name}\n")
                f.write(f"Total run duration: {run_duration:.2f} seconds\n")
                f.write(f"Total tests: {stats_data['total']}\n")
                f.write(f"Passed: {stats_data['passed']}\n")
                f.write(f"Failed: {stats_data['failed']}\n")
                f.write(f"Skipped: {stats_data['skipped']}\n")
                f.write(f"Errors: {stats_data['error']}\n")
                f.write(f"Expected failures (xfail): {stats_data['xfailed']}\n")
                f.write(f"Unexpected passes (xpass): {stats_data['xpassed']}\n")
                f.write(f"Exit code: {exitstatus}\n")
                
                # Add detailed section for failed tests
                if stats_data['failed'] > 0:
                    f.write("\nFailed Tests:\n")
                    f.write("-" * 80 + "\n")
                    failed_count = 0
                    for report in stats.get('failed', []):
                        if report.nodeid.startswith(module_name):
                            failed_count += 1
                            f.write(f"{failed_count}. {report.nodeid}\n")
                            if hasattr(report, "longrepr"):
                                f.write(f"   Error: {report.longrepr}\n")
                    f.write("\n")
                
                # Add detailed section for skipped tests
                if stats_data['skipped'] > 0:
                    f.write("\nSkipped Tests:\n")
                    f.write("-" * 80 + "\n")
                    skipped_count = 0
                    for report in stats.get('skipped', []):
                        if report.nodeid.startswith(module_name):
                            skipped_count += 1
                            f.write(f"{skipped_count}. {report.nodeid}\n")
                            if hasattr(report, "longrepr"):
                                f.write(f"   Reason: {report.longrepr}\n")
                    f.write("\n")
                
                f.write("=" * 80 + "\n")
            
            result_files.append(module_file)
    
    # Print a summary message showing all result files
    if result_files:
        print("\nTest results saved to:")
        for file in result_files:
            print(f"  - {file}")

# Remove since we're handling this in pytest_configure now
@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: Any) -> None:
    """Hook is kept for compatibility but functionality moved to pytest_configure."""
    pass 