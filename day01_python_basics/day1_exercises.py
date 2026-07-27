"""
Day 1: Python Fundamentals Checkpoint
====================================
INSTRUCTIONS:
- Write ALL code yourself. Do not use Cursor, Copilot, or ChatGPT to generate answers.
- Fill in each function/class below.
- When you're done, run this script using `python day1_exercises.py` to test your solutions!
"""

import json
import requests
from typing import List, Dict, Any, Callable

# =====================================================================
# EXERCISE 1: Filtering Dictionaries
# =====================================================================
# Write a function that takes a list of dictionaries and returns only the items
# where a given key's value satisfies a condition (predicate function).
#
# Example:
#   data = [{"name": "CBC", "price": 300}, {"name": "MRI", "price": 4500}]
#   filter_by_condition(data, "price", lambda p: p < 1000)
#   Should return: [{"name": "CBC", "price": 300}]

def filter_by_condition(data: List[Dict[str, Any]], key: str, condition: Callable[[Any], bool]) -> List[Dict[str, Any]]:
    # TODO: Implement this function from scratch
    pass


# =====================================================================
# EXERCISE 2: Object-Oriented Programming (OOP)
# =====================================================================
# Create a Patient class that stores a patient's name, phone number, and a list of booked tests.
# Requirements:
#   1. __init__(self, name: str, phone: str) -> initializes name, phone, and an empty list of tests
#   2. add_test(self, test_name: str, price: float) -> adds a dictionary {"test": test_name, "price": price} to tests
#   3. get_total_bill(self) -> returns the sum of prices for all booked tests
#   4. __str__(self) -> returns a formatted string summary, e.g.:
#      "Patient: Vineet (Ph: 8299597072) - 2 tests booked | Total: Rs. 800"

class Patient:
    # TODO: Implement __init__, add_test, get_total_bill, and __str__
    pass


# =====================================================================
# EXERCISE 3: File I/O & JSON Processing
# =====================================================================
# Write a function that:
#   1. Reads a JSON file containing a list of lab tests (each has "name", "price", "fasting_required").
#   2. Finds all tests where "fasting_required" is True AND "price" is less than max_price.
#   3. Writes the filtered list to a new JSON file specified by output_filename.
#   4. Returns the number of tests written.

def process_and_save_tests(input_filename: str, output_filename: str, max_price: float) -> int:
    # TODO: Implement reading input_filename with open(), filtering, and saving to output_filename with json.dump()
    pass


# =====================================================================
# EXERCISE 4: HTTP APIs with `requests`
# =====================================================================
# Write a function that makes a GET request to a public API, parses the JSON response,
# and returns specific information.
# Using API: https://jsonplaceholder.typicode.com/users
# Return a dictionary mapping user ID to their email address, e.g.:
#   {1: "Sincere@april.biz", 2: "Shanna@melissa.tv", ...}

def fetch_user_emails() -> Dict[int, str]:
    # TODO: Use requests.get(), check status code / raise_for_status(), parse .json(), return dict
    pass


# =====================================================================
# EXERCISE 5: Error Handling & Robust API Calling
# =====================================================================
# Write a function `safe_api_get(url: str, timeout: int = 5) -> Dict[str, Any]` that makes a GET request
# to the provided URL and handles potential errors gracefully:
#   - If a Timeout occurs (requests.exceptions.Timeout), return {"error": "Timeout", "success": False}
#   - If a RequestException occurs (requests.exceptions.RequestException), return {"error": "Request failed", "success": False}
#   - If JSON parsing fails (ValueError or json.JSONDecodeError), return {"error": "Invalid JSON", "success": False}
#   - If successful, return {"data": response.json(), "success": True}

def safe_api_get(url: str, timeout: int = 5) -> Dict[str, Any]:
    # TODO: Implement try/except blocks handling requests exceptions and JSON decode errors
    pass


# =====================================================================
# TEST HARNESS - Run `python day1_exercises.py` to check your work!
# =====================================================================
if __name__ == "__main__":
    print("=== Testing Exercise 1: filter_by_condition ===")
    sample_tests = [
        {"name": "CBC", "price": 300},
        {"name": "Lipid Profile", "price": 800},
        {"name": "MRI Brain", "price": 5500}
    ]
    res1 = filter_by_condition(sample_tests, "price", lambda p: p < 1000)
    print("Result (<1000):", res1)
    print()

    print("=== Testing Exercise 2: Patient OOP ===")
    p = Patient("Vineet Pandey", "8299597072")
    p.add_test("CBC", 300.0)
    p.add_test("Thyroid Profile", 500.0)
    print("Total Bill:", p.get_total_bill())
    print("Summary:", str(p))
    print()

    print("=== Testing Exercise 3: File I/O & JSON ===")
    # Create sample json file for testing
    test_file_data = [
        {"name": "CBC", "price": 300, "fasting_required": False},
        {"name": "Fasting Blood Sugar", "price": 150, "fasting_required": True},
        {"name": "Lipid Profile", "price": 800, "fasting_required": True},
        {"name": "Comprehensive Panel", "price": 2500, "fasting_required": True}
    ]
    with open("sample_tests.json", "w") as f:
        json.dump(test_file_data, f, indent=2)
    
    count = process_and_save_tests("sample_tests.json", "filtered_tests.json", 1000.0)
    print(f"Filtered tests saved: {count}")
    print()

    print("=== Testing Exercise 4: HTTP APIs ===")
    try:
        emails = fetch_user_emails()
        print("Fetched emails (first 3):", dict(list(emails.items())[:3]))
    except Exception as e:
        print("Error fetching emails:", e)
    print()

    print("=== Testing Exercise 5: Safe API Get ===")
    res_ok = safe_api_get("https://jsonplaceholder.typicode.com/todos/1")
    print("Valid request result:", res_ok)
    res_bad = safe_api_get("https://jsonplaceholder.typicode.com/invalid-endpoint-404")
    print("404 request result:", res_bad)
    print("==============================================")
