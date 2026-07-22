"""
Temporary stress testing script for Auditor M2 - Isolated tests
"""
from agents.planner import planner_agent_node, extract_keywords_rule_based, clamp_keywords

def run_stress_tests():
    print("--- Running Isolated Stress Tests ---")
    
    # Test 1: Long query
    try:
        long_q = "neural network " * 1000
        res1 = planner_agent_node({"user_query": long_q})
        print("1. Long Query (10k chars): PASS ->", len(res1["search_keywords"]), res1["search_keywords"])
    except Exception as e:
        print("1. Long Query: FAIL ->", type(e).__name__, e)

    # Test 2: None state
    try:
        res3 = planner_agent_node(None)
        print("2. None State: PASS ->", len(res3["search_keywords"]), res3["search_keywords"])
    except Exception as e:
        print("2. None State: FAIL ->", type(e).__name__, e)

    # Test 3: Numbers only
    try:
        res4 = planner_agent_node({"user_query": "12345 67890 9999"})
        print("3. Numbers Only: PASS ->", len(res4["search_keywords"]), res4["search_keywords"])
    except Exception as e:
        print("3. Numbers Only: FAIL ->", type(e).__name__, e)

    # Test 4: Special characters only (Punctuation)
    try:
        special_q = "!@#$%^&*()_+={}:;\"<>,.?/"
        res2 = planner_agent_node({"user_query": special_q})
        print("4. Special Chars Only: PASS ->", len(res2["search_keywords"]), res2["search_keywords"])
    except Exception as e:
        print("4. Special Chars Only: FAIL ->", type(e).__name__, e)

    # Test 5: Stopwords only
    try:
        stop_q = "the a an and or but in on at with"
        res5 = planner_agent_node({"user_query": stop_q})
        print("5. Stopwords Only: PASS ->", len(res5["search_keywords"]), res5["search_keywords"])
    except Exception as e:
        print("5. Stopwords Only: FAIL ->", type(e).__name__, e)

if __name__ == "__main__":
    run_stress_tests()
