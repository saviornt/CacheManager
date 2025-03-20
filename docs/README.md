# CacheManager Documentation

This directory contains the documentation for the CacheManager project. The documentation is built using [Sphinx](https://www.sphinx-doc.org/).

## Directory Structure

- `source/`: Contains the source RST files for the documentation
  - `api/`: API documentation for the CacheManager classes and modules
  - `advanced/`: Documentation for advanced features
- `build/`: Output directory for the built documentation (created by Sphinx)
- `scripts/`: Helper scripts for documentation maintenance
  - `fix_headers.py`: Script to fix header underlines in RST files
  - `create_placeholders.py`: Script to create placeholder documentation for advanced features

## Building the Documentation

### Prerequisites

- Python 3.6+
- Sphinx
- sphinx-rtd-theme

Install the required packages:

```bash
pip install sphinx sphinx-rtd-theme sphinx-markdown-builder rst2pdf
```

### Build Commands

To build the HTML documentation:

```bash
cd docs
sphinx-build -b html source build/html
```

To build the PDF documentation:

```bash
cd docs
sphinx-build -b pdf source build/pdf
```

To build the Markdown documentation:

```bash
cd docs
sphinx-build -b markdown source build/md
```

## Updating the Documentation

1. Edit the RST files in the `source/` directory
2. Run the helper script to fix header underlines:

   ```bash
   cd docs
   python scripts/fix_headers.py
   ```

3. Build the documentation to verify your changes
4. Check the console output for warnings and errors

## Adding New Documentation

1. Create a new RST file in the appropriate directory
2. Add the file to the appropriate toctree in the parent RST file
3. Follow the existing formatting conventions
4. Run the header fix script to ensure consistent formatting:

   ```bash
   cd docs
   python scripts/fix_headers.py
   ```

5. Build and verify the documentation

## Documentation Conventions

- Use consistent header styles:
  - = for top-level headers (title)
  - `-` for section headers
  - ~ for subsection headers
  - ` for subsubsection headers
- Include code examples with proper syntax highlighting
- Add cross-references to other sections when appropriate
- Document all parameters and return values in function and method descriptions

## Troubleshooting

### Common Issues

- **Header Underline Warnings**: Run the `scripts/fix_headers.py` script to fix header underline length issues
- **Duplicate Object Descriptions**: Add `:no-index:` to the autodoc directive for one of the duplicate objects
- **Missing References**: Ensure that the referenced objects exist and are properly imported

### Building Documentation in Different Formats

If you encounter issues with a specific output format, try building in a different format to isolate the problem. For example, if PDF building fails, try building HTML or Markdown.
