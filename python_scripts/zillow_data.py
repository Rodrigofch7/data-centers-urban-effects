import pandas as pd
import numpy as np
import pytest

# --- Zillow Processing ---
def process_zillow_yearly(df):
    metadata_cols = [col for col in df.columns if not col.startswith('X')]
    date_cols = [col for col in df.columns if col.startswith('X')]
    
    df_long = pd.melt(df, 
                      id_vars=metadata_cols, 
                      value_vars=date_cols, 
                      var_name='Date_Str', 
                      value_name='Estimate')
    
    df_long['Year'] = df_long['Date_Str'].str.lstrip('X').str.split('.').str[0]
    df_long['Estimate'] = pd.to_numeric(df_long['Estimate'], errors='coerce')
    
    yearly_grouped = df_long.groupby(metadata_cols + ['Year'])['Estimate'].mean().reset_index()
    
    final_df = yearly_grouped.pivot(index=metadata_cols, 
                                    columns='Year', 
                                    values='Estimate').reset_index()
    final_df.columns.name = None
    return final_df

# --- Test Suite ---

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
    
    # Check if 'X2023.01.31' style columns are gone and replaced by '2023'
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
        'X2023.02.28': ['InvalidData'] # This should be coerced to NaN
    })
    
    result = process_zillow_yearly(dirty_data)
    # Average of 1000 and NaN should be 1000
    assert result['2023'].iloc[0] == 1000.0

# --- Main Execution Block ---
if __name__ == "__main__":
    # In a real workflow, you'd run `pytest filename.py`
    # For now, we run the actual processing code
    try:
        zillow_data = pd.read_csv('data/zillow_data_zip_code_cook_county.csv')
        zillow_data = zillow_data.rename(columns={'RegionName' : 'ZipCode'})

        result = process_zillow_yearly(zillow_data)
        if 'Unnamed: 0' in result.columns:
            result.drop(columns='Unnamed: 0', inplace=True)

        print(f"Processed Rows: {len(result)}")
        result.to_csv('data/zillow_yearly_estimates_cook_county.csv', index=False)
    except FileNotFoundError:
        print("Data file not found. Skipping main execution, but tests are ready.")