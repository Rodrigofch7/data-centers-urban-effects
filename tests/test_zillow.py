import pytest
import pandas as pd
# Import from: folder_name.file_name
from data_centers_next_door.data_preparation.zillow_data import process_zillow_yearly

@pytest.fixture
def sample_zillow_data():
    """Provides a small mocked version of the Zillow dataset."""
    return pd.DataFrame({
        'ZipCode': [60601, 60601],
        'City': ['Chicago', 'Chicago'],
        'X2023.01.31': [100, 200], # Avg for 2023 should be 150
        'X2023.02.28': [200, 300], # Avg for 2023 should be 250 (Total avg 200)
        'X2024.01.31': [500, 500]  # Avg for 2024 should be 500
    })

def test_column_transformation(sample_zillow_data):
    """Test 1: Check if date columns are correctly converted to year columns."""
    result = process_zillow_yearly(sample_zillow_data)
    
    assert '2023' in result.columns
    assert '2024' in result.columns
    assert 'X2023.01.31' not in result.columns

def test_yearly_averaging_logic(sample_zillow_data):
    """Test 2: Ensure the math for the yearly mean is correct."""
    result = process_zillow_yearly(sample_zillow_data)
    
    # In 2023: (100+200+200+300) / 4 = 200.0
    expected_2023 = 200.0
    actual_2023 = result.loc[result['ZipCode'] == 60601, '2023'].values[0]
    
    assert actual_2023 == expected_2023

def test_handling_invalid_data():
    """Test 3: Ensure non-numeric strings in estimates don't crash the code."""
    dirty_data = pd.DataFrame({
        'ZipCode': [60601],
        'X2023.01.31': ['1000'],
        'X2023.02.28': ['InvalidData'] 
    })
    
    result = process_zillow_yearly(dirty_data)
    assert result['2023'].iloc[0] == 1000.0