import pandas as pd
import csv
import os

def fix_csv_comma_issues(input_file: str, output_file: str) -> pd.DataFrame:
    """
    Fix CSV files where commas within content are causing parsing issues.
    Specifically handles university data with attributes and values.
    
    Args:
        input_file: Path to the input CSV file
        output_file: Path to the fixed output CSV file
    """
    # The expected columns in our data
    expected_columns = ["University", "Attribute", "Value", "Year", "Source"]
    
    # Read the file as raw text first to understand the structure
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Process each line to fix comma issues
    fixed_data = []
    for line in lines:
        if not line.strip():  # Skip empty lines
            continue
            
        # Split by commas
        parts = line.strip().split(',')
        
        # If we have too many parts, there are commas in content
        if len(parts) > len(expected_columns):
            # First two fields are University and Attribute
            university = parts[0]
            attribute = parts[1]
            
            # Special handling for "Number of Clubs" with comma in number
            if attribute == "Number of Clubs" and len(parts) == 6:
                # Combine the split number parts
                value = parts[2] + parts[3]
                year = parts[4]
                source = parts[5]
            else:
                # For other fields, combine all content parts until the last two fields
                # Last two fields are typically Year and Source
                value_parts = parts[2:-2]
                value = ','.join(value_parts)
                year = parts[-2]
                source = parts[-1]
            
            fixed_data.append([university, attribute, value, year, source])
        else:
            # The line has the right number of fields already
            fixed_data.append(parts)
    
    # Create a DataFrame
    df = pd.DataFrame(fixed_data, columns=expected_columns)
    
    # Clean up any specific issues in the data
    # For "Number of Clubs", make sure we have the number in the right format
    mask = df["Attribute"] == "Number of Clubs"
    df.loc[mask, "Value"] = df.loc[mask, "Value"].apply(
        lambda x: x.replace(",", "") if isinstance(x, str) else x
    )
    
    # Write the fixed data with proper quoting
    df.to_csv(output_file, index=False, quoting=csv.QUOTE_NONNUMERIC)
    
    print(f"Fixed CSV file saved to {output_file}")
    print(f"Processed {len(lines)} lines, resulting in {len(df)} data rows")
    
    # Show a sample of the fixed data
    print("\nSample of fixed data:")
    print(df.head())
    
    return df

# Define file paths
input_file = "./perplexity_data.csv"
output_file = "./fixed_perplexity_data.csv"

# Create the output directory if it doesn't exist
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Run the fix script
fixed_df = fix_csv_comma_issues(input_file, output_file)