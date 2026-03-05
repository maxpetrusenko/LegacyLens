REQUIRED_QUERY_SCENARIOS = [
    {
        "id": "main_entry_point",
        "query": "Where is the main entry point?",
        "expected_tokens": ["PROGRAM-ID", "PROCEDURE DIVISION", "STOP RUN"],
    },
    {
        "id": "customer_record_modifiers",
        "query": "Where is CUSTOMER-RECORD modified?",
        "expected_tokens": ["CUSTOMER-RECORD", "MOVE", "WRITE"],
    },
    {
        "id": "calculate_interest_explanation",
        "query": "Explain CALCULATE-INTEREST flow.",
        "expected_tokens": ["CALCULATE-INTEREST", "COMPUTE", "PERFORM"],
    },
    {
        "id": "file_io_operations",
        "query": "Where is file I/O handled?",
        "expected_tokens": ["READ", "WRITE", "OPEN", "CLOSE"],
    },
    {
        "id": "module_x_dependencies",
        "query": "What depends on MODULE-X?",
        "expected_tokens": ["CALL", "PERFORM", "MODULE-X"],
    },
    {
        "id": "error_handling_patterns",
        "query": "Show error handling patterns.",
        "expected_tokens": ["INVALID KEY", "AT END", "ON ERROR"],
    },
]
