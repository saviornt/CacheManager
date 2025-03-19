#!/usr/bin/env python
"""
CacheManager Test Runner
-----------------------

Simple script to run the CacheManager test suite with rich output formatting.
"""

import sys
import time
import subprocess

def colored(text, color):
    """Add color to text for terminal output."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "bold": "\033[1m",
        "underline": "\033[4m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def run_tests():
    """Run the CacheManager test suite."""
    print(colored("\n=== CacheManager Test Suite ===\n", "bold"))
    
    # Run the tests
    start_time = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-v", "-s"],
        capture_output=True,
        text=True
    )
    duration = time.time() - start_time
    
    # Print the output
    lines = result.stdout.splitlines()
    
    # Filter and process lines
    for line in lines:
        if "PASSED" in line:
            line = line.replace("PASSED", colored("PASSED", "green"))
            print(line)
        elif "FAILED" in line:
            line = line.replace("FAILED", colored("FAILED", "red"))
            print(line)
        elif line.strip().startswith("test_"):
            print(colored(line, "cyan"))
        elif "Running test_" in line:
            print(colored("\n" + line, "bold"))
        elif line.strip().startswith("✓"):
            print(colored(line, "green"))
        elif line.strip().startswith("✅"):
            print(colored(line, "green"))
        elif "Added key" in line:
            print(colored(line, "blue"))
        elif "collected" in line and "item" in line:
            print(colored(line, "yellow"))
        elif "===" in line and "===" in line[::-1]:
            print(colored(line, "bold"))
        else:
            print(line)
    
    if result.stderr:
        print(colored("\nWarnings/Errors:", "yellow"))
        print(result.stderr)
    
    # Print summary
    print("\n" + colored("=" * 80, "bold"))
    print(colored(f"Test run completed in {duration:.2f} seconds", "bold"))
    print(colored(f"Exit code: {result.returncode}", 
                 "green" if result.returncode == 0 else "red"))
    print(colored("=" * 80, "bold") + "\n")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests()) 