import pandas as pd

# Define file names
input_file = "with_ASG_Cloud.csv"
output_file = "cloud_with_ASG_with_grouped_ips.csv"

try:
    # Load the dataset
    df = pd.read_csv(input_file)

    # Define the aggregation functions
    # Get all column names
    all_columns = df.columns.tolist()
    
    # Create an aggregation dictionary
    agg_funcs = {}
    
    # Assign an aggregation function for each column
    for col in all_columns:
        if col == 'NETWORK_ADDRESS.Name':
            # For the IP address column, join unique values with a comma
            agg_funcs[col] = lambda x: ','.join(x.astype(str).unique())
        elif col != 'VIRTUAL_MACHINE.externalId':
            # For all other columns (except the group key), take the first value
            agg_funcs[col] = 'first'
            
    # Group by the instance ID and apply the aggregations
    # .reset_index() turns the group key (instance ID) back into a column
    df_grouped = df.groupby('VIRTUAL_MACHINE.externalId').agg(agg_funcs).reset_index()

    # Re-order columns to match the original file's layout
    original_order = [col for col in df.columns if col in df_grouped.columns]
    df_final = df_grouped[original_order]

    # Save the result to a new CSV file
    df_final.to_csv(output_file, index=False)

    print(f"Successfully processed the file.")
    print(f"Original number of rows: {len(df)}")
    print(f"Deduplicated number of rows: {len(df_final)}")
    print(f"Output saved to: {output_file}")

except Exception as e:
    print(f"An error occurred during processing: {e}")