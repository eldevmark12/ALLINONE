"""
Sample Python Code - ALL-in-One Repository
A collection of useful Python examples and utilities
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any


class DataProcessor:
    """A simple class to demonstrate data processing operations."""
    
    def __init__(self, data: List[Any] = None):
        self.data = data or []
    
    def add_item(self, item: Any) -> None:
        """Add an item to the data list."""
        self.data.append(item)
    
    def filter_data(self, condition) -> List[Any]:
        """Filter data based on a condition function."""
        return [item for item in self.data if condition(item)]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the data."""
        return {
            "total_items": len(self.data),
            "data_types": list(set(type(item).__name__ for item in self.data)),
            "timestamp": datetime.now().isoformat()
        }


def read_json_file(filepath: str) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return {}


def write_json_file(filepath: str, data: Dict[str, Any], indent: int = 2) -> bool:
    """Write data to a JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing JSON file: {e}")
        return False


def fibonacci(n: int) -> List[int]:
    """Generate Fibonacci sequence up to n terms."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    
    sequence = [0, 1]
    while len(sequence) < n:
        sequence.append(sequence[-1] + sequence[-2])
    
    return sequence


def calculate_statistics(numbers: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of numbers."""
    if not numbers:
        return {}
    
    sorted_numbers = sorted(numbers)
    n = len(numbers)
    
    return {
        "count": n,
        "sum": sum(numbers),
        "mean": sum(numbers) / n,
        "median": sorted_numbers[n // 2] if n % 2 else (sorted_numbers[n // 2 - 1] + sorted_numbers[n // 2]) / 2,
        "min": min(numbers),
        "max": max(numbers),
        "range": max(numbers) - min(numbers)
    }


def main():
    """Main function demonstrating the sample code."""
    print("=" * 50)
    print("Sample Python Code - ALL-in-One")
    print("=" * 50)
    
    # Demonstrate DataProcessor
    print("\n1. Data Processor Example:")
    processor = DataProcessor([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    even_numbers = processor.filter_data(lambda x: x % 2 == 0)
    print(f"   Even numbers: {even_numbers}")
    print(f"   Summary: {processor.get_summary()}")
    
    # Demonstrate Fibonacci
    print("\n2. Fibonacci Sequence (first 10 terms):")
    fib_sequence = fibonacci(10)
    print(f"   {fib_sequence}")
    
    # Demonstrate Statistics
    print("\n3. Statistics Example:")
    test_data = [12, 15, 18, 20, 22, 25, 28, 30]
    stats = calculate_statistics(test_data)
    print(f"   Data: {test_data}")
    for key, value in stats.items():
        print(f"   {key.capitalize()}: {value}")
    
    print("\n" + "=" * 50)
    print("Sample code execution complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
