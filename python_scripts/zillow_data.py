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