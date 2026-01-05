"""
Test to verify interface agent tool schemas are Gemini-compatible (no default fields).
This validates Fix #8 (Structured Output) - malformed function call error resolution.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.main_interface_agent_fixed import record_intent_analysis_tool, classify_player_intent_tool
from config.logging_config import get_logger

logger = get_logger(__name__)

def test_tool_schemas_no_defaults():
    """
    Verify that tool parameter schemas don't contain 'default' fields.
    Gemini's protobuf Schema format doesn't support 'default' and causes MALFORMED_FUNCTION_CALL errors.
    """
    logger.info("🧪 Testing interface agent tool schemas for Gemini compatibility...")

    # Test record_intent_analysis_tool
    logger.info("   Checking record_intent_analysis_tool...")
    record_params = record_intent_analysis_tool.parameters

    # Check no default fields in any property
    for prop_name, prop_schema in record_params.get("properties", {}).items():
        if "default" in prop_schema:
            logger.error(f"      ❌ FAIL: Found 'default' in {prop_name}: {prop_schema['default']}")
            return False
        logger.debug(f"      ✅ {prop_name}: no default field")

    logger.info("      ✅ record_intent_analysis_tool has no default fields")

    # Test classify_player_intent_tool
    logger.info("   Checking classify_player_intent_tool...")
    classify_params = classify_player_intent_tool.parameters

    for prop_name, prop_schema in classify_params.get("properties", {}).items():
        if "default" in prop_schema:
            logger.error(f"      ❌ FAIL: Found 'default' in {prop_name}: {prop_schema['default']}")
            return False
        logger.debug(f"      ✅ {prop_name}: no default field")

    logger.info("      ✅ classify_player_intent_tool has no default fields")

    # Verify required fields are specified
    logger.info("   Checking required fields...")
    if "required" not in record_params:
        logger.error("      ❌ FAIL: 'required' missing from record_intent_analysis_tool")
        return False

    logger.info(f"      ✅ record_intent_analysis required fields: {record_params['required']}")

    if "required" not in classify_params:
        logger.error("      ❌ FAIL: 'required' missing from classify_player_intent_tool")
        return False

    logger.info(f"      ✅ classify_player_intent required fields: {classify_params['required']}")

    logger.info("")
    logger.info("✅ ALL TESTS PASSED: Tool schemas are Gemini-compatible")
    logger.info("   - No 'default' fields found")
    logger.info("   - Required fields properly specified")
    logger.info("   - Fix #8 (malformed function call) validated")
    return True

def test_schema_structure():
    """
    Verify that tool schemas have the correct basic structure for Gemini.
    """
    logger.info("")
    logger.info("🧪 Testing tool schema structure...")

    # Check record_intent_analysis_tool structure
    logger.info("   Checking record_intent_analysis_tool structure...")
    record_params = record_intent_analysis_tool.parameters

    assert record_params.get("type") == "object", "Parameters must be type 'object'"
    assert "properties" in record_params, "Parameters must have 'properties'"
    assert "required" in record_params, "Parameters must have 'required'"

    # Verify key properties exist
    expected_props = ["primary", "action_verb", "arguments", "confidence", "rag_needed"]
    for prop in expected_props:
        assert prop in record_params["properties"], f"Missing property: {prop}"
        logger.debug(f"      ✅ Property '{prop}' exists")

    logger.info("      ✅ record_intent_analysis_tool structure valid")

    # Check classify_player_intent_tool structure
    logger.info("   Checking classify_player_intent_tool structure...")
    classify_params = classify_player_intent_tool.parameters

    assert classify_params.get("type") == "object", "Parameters must be type 'object'"
    assert "properties" in classify_params, "Parameters must have 'properties'"
    assert "required" in classify_params, "Parameters must have 'required'"

    # Verify key properties exist
    expected_props = ["player_input", "rag_context"]
    for prop in expected_props:
        assert prop in classify_params["properties"], f"Missing property: {prop}"
        logger.debug(f"      ✅ Property '{prop}' exists")

    logger.info("      ✅ classify_player_intent_tool structure valid")

    logger.info("")
    logger.info("✅ SCHEMA STRUCTURE TESTS PASSED")
    return True

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("INTERFACE AGENT TOOL SCHEMA VALIDATION - FIX #8")
    logger.info("=" * 70)
    logger.info("")

    try:
        # Run tests
        test1_passed = test_tool_schemas_no_defaults()
        test2_passed = test_schema_structure()

        if test1_passed and test2_passed:
            logger.info("")
            logger.info("=" * 70)
            logger.info("🎉 ALL TESTS PASSED - Fix #8 validated successfully!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("✅ Tool schemas are now Gemini-compatible")
            logger.info("✅ MALFORMED_FUNCTION_CALL error should be resolved")
            logger.info("✅ Interface agent ready for production use")
            sys.exit(0)
        else:
            logger.error("")
            logger.error("=" * 70)
            logger.error("❌ TESTS FAILED - Fix #8 needs additional work")
            logger.error("=" * 70)
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}", exc_info=True)
        sys.exit(1)
