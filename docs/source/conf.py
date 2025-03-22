# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'CacheManager'
copyright = '2025, CacheManager Team'
author = 'CacheManager Team'
release = '1.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx_autodoc_typehints',
    'rst2pdf.pdfbuilder',
    'sphinx_markdown_builder',
]

# PDF options
pdf_documents = [(
    'index',
    'CacheManager-Documentation',
    'CacheManager Documentation',
    'CacheManager Team'
)]
pdf_stylesheets = ['sphinx', 'a4']
pdf_use_toc = True
pdf_toc_depth = 3

autodoc_typehints = 'description'
autodoc_member_order = 'bysource'
autoclass_content = 'both'
napoleon_google_docstring = True
napoleon_include_init_with_doc = True
napoleon_use_param = True
napoleon_use_rtype = True

templates_path = ['_templates']
exclude_patterns = []

language = 'en'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'  # Using Read the Docs theme
html_static_path = ['_static']
