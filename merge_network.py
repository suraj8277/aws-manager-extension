import pandas as pd

# -----------------------------
# Load data
# -----------------------------
# Replace 'your_file.csv' with your file path or 'your_file.xlsx' if using Excel
df = pd.read_csv('aws_ec2_inventory_linux_20251126_105140.csv')  

# -----------------------------
# Helper function to get IP prefix
# -----------------------------
def ip_prefix(ip):
    parts = ip.split('.')
    return '.'.join(parts[:3]) + '.xx'

# Apply IP prefix to a new column
df['IP_Range'] = df['Private IPv4'].apply(ip_prefix)

# -----------------------------
# Group by Subnet ID and take first row, replacing IP with range
# -----------------------------
grouped = df.groupby('Subnet ID').first().reset_index()
grouped['Private IPv4'] = grouped['IP_Range']

# Drop the helper column
grouped = grouped.drop(columns=['IP_Range'])

# -----------------------------
# Save the result
# -----------------------------
grouped.to_csv('merged_by_subnet.csv', index=False)
print("Merged data saved to 'merged_by_subnet.csv'")

