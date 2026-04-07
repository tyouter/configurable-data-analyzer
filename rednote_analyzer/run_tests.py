"""
Test Runner for Rednote Analyzer
Runs all tests and generates comprehensive test report
"""

import sys
import os
import json
import io
from datetime import datetime

# Set UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_tests():
    """Run all tests and return results"""
    import subprocess
    import time

    print("=" * 80)
    print("REDNOTE ANALYZER - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results = {
        'test_run': {
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': 0,
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': [],
            'details': []
        }
    }

    # Run pytest
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/test_analyzer.py', '-v', '--tb=short'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=300
        )

        results['test_run']['end_time'] = datetime.now().isoformat()

        # Parse output
        output_lines = result.stdout.split('\n')
        for line in output_lines:
            if '::' in line and 'PASSED' in line:
                results['test_run']['details'].append({
                    'test': line.strip(),
                    'status': 'PASSED'
                })
                results['test_run']['passed'] += 1
                results['test_run']['total_tests'] += 1
            elif '::' in line and 'FAILED' in line:
                results['test_run']['details'].append({
                    'test': line.strip(),
                    'status': 'FAILED'
                })
                results['test_run']['failed'] += 1
                results['test_run']['total_tests'] += 1

        # Check for summary line
        for line in output_lines:
            if 'passed' in line.lower() and 'failed' in line.lower():
                results['test_run']['summary'] = line.strip()

        # Add stderr if any
        if result.stderr:
            results['test_run']['stderr'] = result.stderr

        results['test_run']['returncode'] = result.returncode
        results['test_run']['success'] = result.returncode == 0

        # Show output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

    except subprocess.TimeoutExpired:
        results['test_run']['end_time'] = datetime.now().isoformat()
        results['test_run']['errors'].append('Test execution timed out after 300 seconds')
        results['test_run']['success'] = False

    except Exception as e:
        results['test_run']['end_time'] = datetime.now().isoformat()
        results['test_run']['errors'].append(f'Error running tests: {str(e)}')
        results['test_run']['success'] = False

    # Calculate duration
    if results['test_run']['start_time'] and results['test_run']['end_time']:
        start = datetime.fromisoformat(results['test_run']['start_time'])
        end = datetime.fromisoformat(results['test_run']['end_time'])
        results['test_run']['duration_seconds'] = (end - start).total_seconds()

    return results


def print_test_results(results):
    """Print test results in a formatted way"""
    print()
    print("=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    test_run = results['test_run']

    print(f"Start Time: {test_run['start_time']}")
    print(f"End Time: {test_run['end_time']}")
    print(f"Duration: {test_run['duration_seconds']:.2f} seconds")
    print()

    print(f"Total Tests: {test_run['total_tests']}")
    print(f"Passed: {test_run['passed']}")
    print(f"Failed: {test_run['failed']}")
    print()

    if 'summary' in test_run:
        print(f"Summary: {test_run['summary']}")

    if test_run['errors']:
        print()
        print("Errors:")
        for error in test_run['errors']:
            print(f"  - {error}")

    print()
    if test_run['success']:
        print("[OK] ALL TESTS PASSED")
    else:
        print("[ERROR] SOME TESTS FAILED")

    print("=" * 80)


def save_test_results(results, output_path=None):
    """Save test results to JSON file"""
    if output_path is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'test_results.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return output_path


def main():
    """Main entry point"""
    print()
    print("Starting Rednote Analyzer Test Suite...")
    print()

    # Run tests
    results = run_tests()

    # Print results
    print_test_results(results)

    # Save results
    output_path = save_test_results(results)
    print(f"\nTest results saved to: {output_path}")

    # Return exit code
    return 0 if results['test_run']['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
