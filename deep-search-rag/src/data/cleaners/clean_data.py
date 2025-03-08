import pandas as pd
import os
from datetime import datetime

def merge_datasets(perplexity_file: str, clean_docs_file: str, output_file: str) -> pd.DataFrame:
    """
    Merge two university data files into a single dataset with standardized headers.
    Preserves ALL data from perplexity_file while properly handling clean_docs.
    
    Args:
        perplexity_file: Path to the perplexity dataset CSV
        clean_docs_file: Path to the clean_docs dataset CSV
        output_file: Path to save the merged output CSV
    """
    print(f"Processing Perplexity data from {perplexity_file}")
    print(f"Processing Clean Docs data from {clean_docs_file}")
    
    # Load both datasets
    try:
        perplexity_df = pd.read_csv(perplexity_file)
        print(f"Loaded Perplexity data: {len(perplexity_df)} rows")
        print(f"Perplexity columns: {perplexity_df.columns.tolist()}")
    except Exception as e:
        print(f"Error loading Perplexity data: {e}")
        perplexity_df = pd.DataFrame()
    
    try:
        clean_docs_df = pd.read_csv(clean_docs_file)
        print(f"Loaded Clean Docs data: {len(clean_docs_df)} rows")
        print(f"Clean Docs columns: {clean_docs_df.columns.tolist()}")
    except Exception as e:
        print(f"Error loading Clean Docs data: {e}")
        clean_docs_df = pd.DataFrame()
    
    # Transform data to the new format
    merged_data = []
    
    # 1. Process Perplexity data - PRESERVE ALL ROWS
    if not perplexity_df.empty:
        for _, row in perplexity_df.iterrows():
            university = row.get('university', '')
            attribute = row.get('attribute', '')
            value = row.get('value', '')
            source = row.get('source', '')
            last_updated = row.get('last_updated', '')
            
            # Format file_name (university)
            file_name = university.strip() if isinstance(university, str) else "Unknown"
            
            # Format meta_data - include source here as requested
            meta_data = f"Source: {source}, Attribute: {attribute}" if source else f"Attribute: {attribute}"
            
            # Format the content
            content = value
            
            # Use original last_updated if available, otherwise current timestamp
            if not last_updated or pd.isna(last_updated) or last_updated == '0':
                last_updated = datetime.now().strftime('%Y-%m-%d')
            
            # Add EVERY row from perplexity_df to merged_data
            merged_data.append({
                'file_name': file_name,
                'meta_data': meta_data,
                'content': content,
                'last_updated': last_updated
            })
    
    # 2. Process Clean Docs data - can be merged/deduplicated
    if not clean_docs_df.empty:
        for _, row in clean_docs_df.iterrows():
            university = row.get('university', '')
            metric_name = row.get('metric_name', '')
            value = row.get('value', '')
            year = row.get('year', '')
            
            # Format the content with year if available
            content = value
            if year and str(year).strip() and str(year).strip() != 'nan':
                if "Year" not in content:
                    content = f"{content} (Year {year})"
            
            # Format file_name (university)
            file_name = university.strip() if isinstance(university, str) else "Unknown"
            
            # Format meta_data
            meta_data = f"Metric: {metric_name}"
            
            # Use current timestamp for last_updated
            last_updated = datetime.now().strftime('%Y-%m-%d')
            
            # Check if this is a duplicate of perplexity data
            is_duplicate = False
            for existing_row in merged_data:
                if (existing_row['file_name'] == file_name and 
                    existing_row['content'] == content):
                    is_duplicate = True
                    break
            
            # Only add if not a duplicate
            if not is_duplicate:
                merged_data.append({
                    'file_name': file_name,
                    'meta_data': meta_data,
                    'content': content,
                    'last_updated': last_updated
                })
    
    # Create merged DataFrame
    merged_df = pd.DataFrame(merged_data)
    
    # Clean up content field
    merged_df['content'] = merged_df['content'].apply(lambda x: str(x).strip())
    
    # Sort by file_name
    merged_df = merged_df.sort_values('file_name')
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Save to output file
    merged_df.to_csv(output_file, index=False)
    
    # Print summary
    perplexity_count = len(perplexity_df) if not perplexity_df.empty else 0
    clean_docs_count = len(clean_docs_df) if not clean_docs_df.empty else 0
    merged_count = len(merged_df)
    
    print(f"Summary:")
    print(f"  - Perplexity data rows: {perplexity_count}")
    print(f"  - Clean Docs data rows: {clean_docs_count}")
    print(f"  - Total merged rows: {merged_count}")
    print(f"  - All {perplexity_count} perplexity rows preserved")
    print(f"  - {merged_count - perplexity_count} rows added from clean_docs")
    print(f"Merged dataset saved to {output_file}")
    
    return merged_df

def create_enhanced_dataset(input_file: str, output_file: str) -> pd.DataFrame:
    """
    Create an enhanced dataset with better organization and grouping of related information.
    
    Args:
        input_file: Path to the merged dataset
        output_file: Path to save the enhanced dataset
    """
    # Read the merged dataset
    df = pd.read_csv(input_file)
    print(f"Creating enhanced dataset from {len(df)} rows")
    
    # Group related metrics for the same university
    universities = df['file_name'].unique()
    
    enhanced_data = []
    for university in universities:
        university_data = df[df['file_name'] == university]
        
        # Process each row from original dataset
        for _, row in university_data.iterrows():
            # Keep every row intact
            enhanced_data.append({
                'file_name': row['file_name'],
                'meta_data': row['meta_data'],
                'content': row['content'],
                'last_updated': row['last_updated']
            })
    
    # Create enhanced DataFrame
    enhanced_df = pd.DataFrame(enhanced_data)
    
    # Sort by file_name
    enhanced_df = enhanced_df.sort_values('file_name')
    
    # Save to output file
    enhanced_df.to_csv(output_file, index=False)
    print(f"Enhanced dataset saved to {output_file} with {len(enhanced_df)} rows")
    
    return enhanced_df

# Define file paths
perplexity_file = "./fixed_perplexity_data.csv"
clean_docs_file = "./fixed_clean_docs.csv"
merged_output = "./merged_university_data.csv"
enhanced_output = "./enhanced_university_data.csv"

# Run the merger
merged_df = merge_datasets(perplexity_file, clean_docs_file, merged_output)

# Create enhanced dataset - simply preserves all rows
enhanced_df = create_enhanced_dataset(merged_output, enhanced_output)

print("Data processing complete!")