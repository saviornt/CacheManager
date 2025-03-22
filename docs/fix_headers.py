#!/usr/bin/env python3
"""Script to fix header underline lengths in RST files."""

import re
import glob


def fix_header_underlines(file_path):
    """
    Fix header underlines in RST files to match the length of the header text.
    
    Args:
        file_path: Path to the RST file to fix
    
    Returns:
        bool: True if changes were made, False otherwise
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find headers and their underlines
    pattern = r'([^\n]+)\n([=\-~`]+)\n'
    
    def replace_underline(match):
        header_text = match.group(1)
        underline_char = match.group(2)[0]  # Get the first character of the underline
        # Create a new underline with the same length as the header text
        new_underline = underline_char * len(header_text)
        return f"{header_text}\n{new_underline}\n"
    
    # Replace headers and their underlines
    new_content = re.sub(pattern, replace_underline, content)
    
    # Check if changes were made
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed headers in {file_path}")
        return True
    return False


def main():
    """Fix header underlines in all RST files in the docs directory"""
    # Find all RST files recursively
    rst_files = glob.glob("docs/source/**/*.rst", recursive=True)
    
    changes_made = 0
    for file_path in rst_files:
        if fix_header_underlines(file_path):
            changes_made += 1
    
    print(f"Fixed headers in {changes_made} files")


if __name__ == "__main__":
    main() 