import sys
import subprocess
import datetime
from pathlib import Path

def main():
    """Run tests and save detailed output to a file"""
    # Create a directory for test results if it doesn't exist
    results_dir = Path("test_results")
    results_dir.mkdir(exist_ok=True)
    
    # Create a unique filename for this test run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"test_output_{timestamp}.log"
    
    # Run the tests with pytest and capture the output
    test_files = ["tests/test_cache_manager.py"]
    
    print(f"Running tests and saving output to {output_file}...")
    
    # Open the output file
    with open(output_file, "w") as f:
        # Write header
        f.write(f"CacheManager Test Run - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # Run tests and capture output
        for test_file in test_files:
            f.write(f"Running tests in {test_file}\n")
            f.write("-" * 80 + "\n\n")
            
            # Run the test and capture output
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "-s"],
                capture_output=True,
                text=True
            )
            
            # Write output to file
            f.write(result.stdout)
            if result.stderr:
                f.write("\nERRORS/WARNINGS:\n")
                f.write(result.stderr)
            
            f.write("\n\n")
            
        # Add summary
        f.write("\nTest Run Summary:\n")
        f.write("-" * 80 + "\n")
        f.write(f"Completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Exit code: {result.returncode}\n")
    
    print(f"Test run completed. Results saved to {output_file}")
    
    # Also display the output in the console
    with open(output_file, "r") as f:
        print("\n" + "=" * 80)
        print("TEST OUTPUT:")
        print("=" * 80 + "\n")
        print(f.read())

if __name__ == "__main__":
    main() 