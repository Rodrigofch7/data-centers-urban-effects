import pandas as pd

zillow_data = pd.read_csv('data/zillow_data_zip_code_cook_county.csv')

zillow_data = zillow_data.rename(columns={'RegionName' : 'ZipCode'})



def process_zillow_yearly(df):
    # 1. Identify metadata columns (all columns that don't start with 'X')
    metadata_cols = [col for col in df.columns if not col.startswith('X')]
    
    # 2. Identify date columns (all columns starting with 'X')
    date_cols = [col for col in df.columns if col.startswith('X')]
    
    # 3. Melt the dataframe to long format
    # This turns date columns into a single 'Date_Str' column
    df_long = pd.melt(df, 
                      id_vars=metadata_cols, 
                      value_vars=date_cols, 
                      var_name='Date_Str', 
                      value_name='Estimate')
    
    # 4. Extract the Year from the Date_Str (e.g., 'X2025.03.31' -> '2025')
    # We strip the 'X' and take the first part before the first dot
    df_long['Year'] = df_long['Date_Str'].str.lstrip('X').str.split('.').str[0]
    
    # Ensure Estimate is numeric
    df_long['Estimate'] = pd.to_numeric(df_long['Estimate'], errors='coerce')
    
    # 5. Group by all metadata and the Year, then calculate the average
    yearly_grouped = df_long.groupby(metadata_cols + ['Year'])['Estimate'].mean().reset_index()
    
    # 6. Pivot the 'Year' column back to horizontal columns
    # This keeps one row per ZipCode/Region while having a column for each year
    final_df = yearly_grouped.pivot(index=metadata_cols, 
                                    columns='Year', 
                                    values='Estimate').reset_index()
    
    # Optional: Clean up the column name levels if needed
    final_df.columns.name = None
    
    return final_df

# Apply the function
result = process_zillow_yearly(zillow_data)
result.drop(columns='Unnamed: 0', inplace=True)

print(len(result))

result.to_csv('data/zillow_yearly_estimates_cook_county.csv', index=False)