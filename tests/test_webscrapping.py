import pytest
# Reference: folder_name.file_name
from python_scripts.webscrapping_data_centers import (
    parse_datacenter_html, 
    CITIES, 
    CITY_TO_STATE
)

def test_city_to_state_mapping_integrity():
    """Test: Ensure every city in the scraper list has a state mapping."""
    for city_name, _ in CITIES:
        assert city_name in CITY_TO_STATE, f"{city_name} is missing from CITY_TO_STATE"

def test_html_parsing_extraction():
    """Test: Verify that the scraper correctly pulls data from a sample HTML block."""
    sample_html = """
    <div class="ui card">
        <div class="header">Test Facility</div>
        <div class="description">
            Test Operator<br/>
            456 Server Lane<br/>
            90210<br/>
            Los Angeles
        </div>
    </div>
    """
    results = parse_datacenter_html(sample_html, "Los Angeles")
    
    assert len(results) == 1
    assert results[0]["facility"] == "Test Facility"
    assert results[0]["operator"] == "Test Operator"
    assert results[0]["zip_code"] == "90210"
    assert results[0]["state"] == "CA"

def test_parsing_handles_missing_fields():
    """Test: Verify the scraper doesn't crash if HTML fields are missing."""
    empty_html = '<div class="ui card"></div>'
    results = parse_datacenter_html(empty_html, "Chicago")
    
    assert results[0]["facility"] == "N/A"
    assert results[0]["operator"] == "N/A"