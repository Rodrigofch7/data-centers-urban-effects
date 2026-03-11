import pandas as pd
from data_centers_next_door.data_preparation.chicago_dc_clean_merge import (
    clean_scraped_datacenters,
    clean_datacenter_housing_data,
    clean_monthHHC,
    add_housing_cost_scores)

def main():
    # Checking clean_scraped_datacenters, cleaned addresses are not duplicated:
    cleaned_df = clean_scraped_datacenters()

    if "street_standard" in cleaned_df.columns:
        duplicated_addresses = cleaned_df["street_standard"].duplicated().sum()
        assert duplicated_addresses == 0
    elif "street" in cleaned_df.columns:
        duplicated_addresses = cleaned_df["street"].duplicated().sum()
        assert duplicated_addresses == 0
    else:
        raise AssertionError
    
    # Checking clean_datacenter_housing_data, that every DataCenter_Code starts with DC:
    merged_dc_housing_df = clean_datacenter_housing_data()

    assert "DataCenter_Code" in merged_dc_housing_df.columns
    
    starts_with_dc = merged_dc_housing_df["DataCenter_Code"].astype(str).str.startswith("DC").all()
    
    assert starts_with_dc

    # Checking clean_monthHHC, that Zipcode and Housing_Costs_Score columns exist:
    hhhc_df = clean_monthHHC()

    assert "Zipcode" in hhhc_df.columns

    assert "Housing_Costs_Score" in hhhc_df.columns

    # Checking add_housing_cost_scores, that random values in columns are not empty:
    final_df = add_housing_cost_scores()

    random_hc_row = hhhc_df.sample(1, random_state=42).iloc[0]
    hc_score_value = random_hc_row["Housing_Costs_Score"]
    assert pd.notna(hc_score_value) and str(hc_score_value).strip() != ""

    assert "HC_Score_Before" in final_df.columns
    before_nonempty = final_df[final_df["HC_Score_Before"].notna()]
    assert len(before_nonempty) > 0
    
    random_before_row = before_nonempty.sample(1, random_state=42).iloc[0]
    before_value = random_before_row["HC_Score_Before"]
    assert pd.notna(before_value) and str(before_value).strip() != ""

    assert "HC_Score_After" in final_df.columns
    after_nonempty = final_df[final_df["HC_Score_After"].notna()]
    assert len(after_nonempty) > 0

    random_after_row = after_nonempty.sample(1, random_state=42).iloc[0]
    after_value = random_after_row["HC_Score_After"]
    assert pd.notna(after_value) and str(after_value).strip() != ""

if __name__ == "__main__":
    main()