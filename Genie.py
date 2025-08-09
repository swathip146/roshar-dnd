"""
This script provides a command-line interface for two main applications:
1. A Retrieval-Augmented Generation (RAG) application that can answer questions based on a provided set of documents (TXT, CSV, PDF, or Confluence).
2. A data analysis application that can perform analysis on CSV files using natural language prompts.

The script uses the hwtgenielib library to build and run pipelines for these tasks.
"""
# Import necessary libraries and modules
import pandas as pd
import os
import glob
import shutil
import webbrowser
import pathlib
import time
import itertools
import threading
import sys
import json
from urllib.parse import urlparse
from pdf_parser import parse_pdf
from hwtgenielib import Pipeline, Document, component
from Analysis.helpers.results import display_results, interactive_options
from hwtgenielib.components.retrievers import QdrantEmbeddingRetriever
from hwtgenielib.document_stores.qdrant import QdrantDocumentStore
import matplotlib.pyplot as plt
from hwtgenielib.components.embedders import HWTTextEmbedder, HWTDocumentEmbedder
from hwtgenielib.components.writers import DocumentWriter
from hwtgenielib.components.builders import PromptBuilder, ChatPromptBuilder, AnswerBuilder
from hwtgenielib.components.generators import HWTGenerator
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator, AppleGenAIGeminiChatGenerator
from hwtgenielib.components.preprocessors import DocumentSplitter, DocumentCleaner
from hwtgenielib.components.rankers import HWTSimilarityRanker
from hwtgenielib.dataclasses import ChatMessage
from hwtgenielib.components.analysis import (
    Dataset, PromptGenerator as DataAnalysisPromptGenerator, CodeGenerator,
    CodeExecutor, ResultsExporter
)
# Confluence-related imports
from hwtgenielib.components.fetchers.confluence import ConfluenceFetcher
from hwtgenielib.components.converters.confluence import ConfluencePageToDocument
from hwtgenielib.utils import Secret
from bs4 import BeautifulSoup
import re

# Configuration variables
TOP_K_RETRIEVAL = 300  # Number of top documents to retrieve for RAG
TOP_K_SIMILARITY = 10  # Number of top documents from similarity ranker

@component
class EnhancedConfluenceTableParser:
    """
    Enhanced HTML table parser that properly handles merged cells (rowspan/colspan)
    and improves table extraction from Confluence pages.
    """
    
    @component.output_types(documents=list)
    def run(self, pages: list):
        """
        Parse Confluence pages with enhanced table handling.
        
        Args:
            pages: List of Confluence page objects
            
        Returns:
            List of Document objects with improved table parsing
        """
        documents = []
        
        for page in pages:
            try:
                # Get the HTML content from the page
                html_content = page.body if hasattr(page, 'body') else str(page)
                
                # Parse and enhance the HTML
                enhanced_content = self._parse_html_with_enhanced_tables(html_content)
                
                # Create document with enhanced content
                meta = {
                    'title': getattr(page, 'title', 'Untitled'),
                    'id': getattr(page, 'id', 'unknown'),
                    'url': getattr(page, 'url', ''),
                    'space': getattr(page, 'space', ''),
                    'type': 'confluence_enhanced'
                }
                
                from hwtgenielib import Document
                doc = Document(content=enhanced_content, meta=meta)
                documents.append(doc)
                
            except Exception as e:
                print(f"Error parsing page: {e}")
                # Fallback to original content if parsing fails
                fallback_content = str(page)
                meta = {'title': 'Parse Error', 'error': str(e)}
                from hwtgenielib import Document
                doc = Document(content=fallback_content, meta=meta)
                documents.append(doc)
        
        return {"documents": documents}
    
    def _parse_html_with_enhanced_tables(self, html_content):
        """Parse HTML content with enhanced table handling."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all tables and process them
            tables = soup.find_all('table')
            
            for table in tables:
                enhanced_table_text = self._parse_table_with_merged_cells(table)
                
                # Replace the table with our enhanced text representation
                table_placeholder = soup.new_tag('div', **{'class': 'enhanced-table'})
                table_placeholder.string = enhanced_table_text
                table.replace_with(table_placeholder)
            
            # Extract text content
            text_content = soup.get_text(separator='\n', strip=True)
            
            # Clean up extra whitespace
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            
            return text_content
            
        except Exception as e:
            print(f"Error parsing HTML: {e}")
            # Fallback to simple text extraction
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text()
    
    def _parse_table_with_merged_cells(self, table):
        """
        Parse an HTML table accounting for merged cells (rowspan/colspan).
        Returns a formatted text representation of the table.
        """
        try:
            rows = table.find_all('tr')
            if not rows:
                return "[Empty Table]"
            
            # First pass: determine table dimensions accounting for merged cells
            max_cols = 0
            row_data = []
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                col_count = sum(int(cell.get('colspan', 1)) for cell in cells)
                max_cols = max(max_cols, col_count)
            
            # Create a matrix to track cell positions
            table_matrix = []
            
            for row_idx, row in enumerate(rows):
                if row_idx >= len(table_matrix):
                    table_matrix.append([None] * max_cols)
                
                cells = row.find_all(['td', 'th'])
                col_idx = 0
                
                for cell in cells:
                    # Find the next available column
                    while col_idx < max_cols and table_matrix[row_idx][col_idx] is not None:
                        col_idx += 1
                    
                    if col_idx >= max_cols:
                        break
                    
                    # Get cell content and attributes
                    cell_text = cell.get_text(strip=True)
                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    
                    # Fill the matrix for this cell and its spans
                    for r in range(row_idx, min(row_idx + rowspan, len(rows))):
                        # Ensure we have enough rows in the matrix
                        while r >= len(table_matrix):
                            table_matrix.append([None] * max_cols)
                        
                        for c in range(col_idx, min(col_idx + colspan, max_cols)):
                            if r == row_idx and c == col_idx:
                                # Original cell position gets the content
                                table_matrix[r][c] = cell_text
                            else:
                                # Merged positions get a placeholder
                                table_matrix[r][c] = f"↖ {cell_text}" if cell_text else "↖"
                    
                    col_idx += colspan
            
            # Format the table as text
            table_text = []
            table_text.append("\n[TABLE START]")
            
            # Add column headers if first row looks like headers
            if table_matrix and any(cell and cell.strip() for cell in table_matrix[0]):
                header_row = " | ".join(str(cell or "").strip() for cell in table_matrix[0])
                table_text.append(f"Headers: {header_row}")
                table_text.append("-" * min(80, len(header_row) + 10))
                start_row = 1
            else:
                start_row = 0
            
            # Add data rows
            for i, row in enumerate(table_matrix[start_row:], start_row + 1):
                row_text = " | ".join(str(cell or "").strip() for cell in row)
                if row_text.strip():  # Only add non-empty rows
                    table_text.append(f"Row {i}: {row_text}")
            
            table_text.append("[TABLE END]\n")
            
            return "\n".join(table_text)
            
        except Exception as e:
            print(f"Error parsing table: {e}")
            # Fallback to simple table text extraction
            return f"\n[TABLE - Simple Parse]\n{table.get_text(separator=' | ', strip=True)}\n[TABLE END]\n"

@component
class CombinedConfluenceParser:
    """
    Combines the default ConfluencePageToDocument with EnhancedConfluenceTableParser
    to preserve most content while improving table extraction.
    """
    
    @component.output_types(documents=list)
    def run(self, pages: list):
        """
        Parse Confluence pages using default parser for content structure and enhanced parser for tables.
        
        Args:
            pages: List of Confluence page objects
            
        Returns:
            List of Document objects with combined parsing results
        """
        documents = []
        
        for i, page in enumerate(pages):
            try:
                # Get the HTML content from the page
                html_content = page.body if hasattr(page, 'body') else str(page)
                
                # Use default parser for general content structure
                default_parser = ConfluencePageToDocument(parse_html=True)
                default_result = default_parser.run(pages=[page])
                default_doc = default_result.get("documents", [None])[0]
                
                # Check if there are tables in the HTML content
                soup = BeautifulSoup(html_content, 'html.parser')
                tables = soup.find_all('table')
                
                if tables and default_doc:
                    #print(f"  Found {len(tables)} table(s) in page {i+1}, using enhanced parsing for tables")
                    
                    # Extract enhanced table content
                    enhanced_table_content = self._extract_enhanced_tables(html_content)
                    
                    # Combine default content with enhanced tables
                    combined_content = self._replace_tables_in_content(
                        default_doc.content,
                        enhanced_table_content
                    )
                    
                    # Create combined document
                    meta = default_doc.meta.copy() if hasattr(default_doc, 'meta') else {}
                    meta.update({
                        'title': getattr(page, 'title', f'Document_{i+1}'),
                        'id': getattr(page, 'id', 'unknown'),
                        'url': getattr(page, 'url', ''),
                        'space': getattr(page, 'space', ''),
                        'parsing_method': 'combined_enhanced_tables'
                    })
                    
                    from hwtgenielib import Document
                    doc = Document(content=combined_content, meta=meta)
                    documents.append(doc)
                    
                elif default_doc:
                    # No tables found, use default parsing only
                    #print(f"  No tables found in page {i+1}, using default parsing")
                    meta = default_doc.meta.copy() if hasattr(default_doc, 'meta') else {}
                    meta.update({
                        'title': getattr(page, 'title', f'Document_{i+1}'),
                        'parsing_method': 'default_only'
                    })
                    from hwtgenielib import Document
                    doc = Document(content=default_doc.content, meta=meta)
                    documents.append(doc)
                    
                else:
                    # Fallback: basic page content
                    print(f"  Default parser failed for page {i+1}, using fallback")
                    content = str(page)
                    meta = {
                        'title': getattr(page, 'title', f'Document_{i+1}'),
                        'parsing_method': 'fallback'
                    }
                    from hwtgenielib import Document
                    doc = Document(content=content, meta=meta)
                    documents.append(doc)
                    
            except Exception as e:
                print(f"Error parsing page {i+1}: {e}")
                # Create error document
                meta = {'title': 'Parse Error', 'error': str(e), 'parsing_method': 'error'}
                from hwtgenielib import Document
                doc = Document(content=f"Error parsing page: {e}", meta=meta)
                documents.append(doc)
        
        return {"documents": documents}
    
    def _extract_enhanced_tables(self, html_content):
        """
        Extract tables using enhanced parser and return table content.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            enhanced_tables = []
            
            # Find all tables and process them with enhanced parsing
            tables = soup.find_all('table')
            
            for table in tables:
                enhanced_table_text = self._parse_table_with_merged_cells(table)
                enhanced_tables.append(enhanced_table_text)
            
            return enhanced_tables
            
        except Exception as e:
            print(f"Error extracting enhanced tables: {e}")
            return []
    
    def _parse_table_with_merged_cells(self, table):
        """
        Reuse the enhanced table parsing logic from EnhancedConfluenceTableParser.
        """
        try:
            rows = table.find_all('tr')
            if not rows:
                return "[Empty Table]"
            
            # First pass: determine table dimensions accounting for merged cells
            max_cols = 0
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                col_count = sum(int(cell.get('colspan', 1)) for cell in cells)
                max_cols = max(max_cols, col_count)
            
            # Create a matrix to track cell positions
            table_matrix = []
            
            for row_idx, row in enumerate(rows):
                if row_idx >= len(table_matrix):
                    table_matrix.append([None] * max_cols)
                
                cells = row.find_all(['td', 'th'])
                col_idx = 0
                
                for cell in cells:
                    # Find the next available column
                    while col_idx < max_cols and table_matrix[row_idx][col_idx] is not None:
                        col_idx += 1
                    
                    if col_idx >= max_cols:
                        break
                    
                    # Get cell content and attributes
                    cell_text = cell.get_text(strip=True)
                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    
                    # Fill the matrix for this cell and its spans
                    for r in range(row_idx, min(row_idx + rowspan, len(rows))):
                        # Ensure we have enough rows in the matrix
                        while r >= len(table_matrix):
                            table_matrix.append([None] * max_cols)
                        
                        for c in range(col_idx, min(col_idx + colspan, max_cols)):
                            if r == row_idx and c == col_idx:
                                # Original cell position gets the content
                                table_matrix[r][c] = cell_text
                            else:
                                # Merged positions get a placeholder
                                table_matrix[r][c] = f"↖ {cell_text}" if cell_text else "↖"
                    
                    col_idx += colspan
            
            # Format the table as text
            table_text = []
            table_text.append("\n[TABLE START]")
            
            # Add column headers if first row looks like headers
            if table_matrix and any(cell and cell.strip() for cell in table_matrix[0]):
                header_row = " | ".join(str(cell or "").strip() for cell in table_matrix[0])
                table_text.append(f"Headers: {header_row}")
                table_text.append("-" * min(80, len(header_row) + 10))
                start_row = 1
            else:
                start_row = 0
            
            # Add data rows
            for i, row in enumerate(table_matrix[start_row:], start_row + 1):
                row_text = " | ".join(str(cell or "").strip() for cell in row)
                if row_text.strip():  # Only add non-empty rows
                    table_text.append(f"Row {i}: {row_text}")
            
            table_text.append("[TABLE END]\n")
            
            return "\n".join(table_text)
            
        except Exception as e:
            print(f"Error parsing table: {e}")
            # Fallback to simple table text extraction
            return f"\n[TABLE - Simple Parse]\n{table.get_text(separator=' | ', strip=True)}\n[TABLE END]\n"
    
    def _replace_tables_in_content(self, default_content, enhanced_tables):
        """
        Replace table content in default parsed content with enhanced table content.
        """
        try:
            if not enhanced_tables:
                return default_content + "\n\n[PARSING INFO: No tables to enhance]"
            
            # For now, append enhanced tables to the default content
            # This is a simplified approach - in practice you might want more sophisticated replacement
            combined_content = default_content
            
            for i, table_content in enumerate(enhanced_tables):
                combined_content += f"\n\n{table_content}"
            
            combined_content += f"\n\n[PARSING INFO: Combined default content with {len(enhanced_tables)} enhanced table(s)]"
            
            return combined_content
            
        except Exception as e:
            print(f"Error replacing tables: {e}")
            return default_content + f"\n\n[PARSING INFO: Error enhancing tables: {e}]"

def is_valid_url(url):
    """
    Validate if the provided string is a valid URL.
    
    Args:
        url (str): The URL string to validate
        
    Returns:
        bool: True if valid URL, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def get_confluence_url():
    """
    Get and validate Confluence URL from user input.
    
    Returns:
        str: Valid Confluence URL
    """
    while True:
        confluence_url = input("Please enter the Confluence page URL: ").strip()
        
        if not confluence_url:
            print("Error: Confluence URL is required.")
            continue
            
        if not is_valid_url(confluence_url):
            print("Error: Please provide a valid URL (e.g., https://seg-confluence.csg.apple.com/wiki/spaces/...)")
            print("The URL should start with 'http://' or 'https://' and include the domain name.")
            continue
            
        # Additional check for common Confluence URL patterns
        if 'seg-confluence.csg.apple.com' not in confluence_url.lower():
            print("Warning: This doesn't appear to be a typical Confluence URL. Confluence URLs usually contain 'confluence.csg.apple.com'in the path")
            confirm = input("Do you want to proceed with this URL? (yes/no): ").lower().strip()
            if confirm not in ['yes', 'y']:
                continue
                
        return confluence_url

def get_confluence_pat_token():
    """
    Get Confluence PAT token from user input with help option.
    
    Returns:
        str: Valid PAT token
    """
    # print("\nConfluence PAT (Personal Access Token) is required for authentication.")
    # print("Type 'help' if you need instructions on how to generate a PAT token.")
    
    while True:
        pat_token = input("Please enter your Confluence PAT token (or 'help' for instructions): ").strip()
        
        if pat_token.lower() == 'help':
            print("\n" + "="*70)
            print("HOW TO GENERATE CONFLUENCE PAT TOKEN:")
            print("="*70)
            print("Generate the token in Confluence under Profile > Settings > PAT Token")
            print()
            print("Detailed steps:")
            print("1. Log into your Confluence instance")
            print("2. Click your profile picture in the top right corner")
            print("3. Select 'Profile' from the dropdown menu")
            print("4. Click on 'Settings' tab")
            print("5. Look for 'PAT Token' or 'Personal Access Token' section")
            print("6. Click 'Create token' or 'Generate new token'")
            print("7. Give your token a name (e.g., 'Genie RAG Access')")
            print("8. Set appropriate permissions (usually 'Read' access is sufficient)")
            print("9. Copy the generated token immediately (you won't see it again)")
            print("="*70)
            print()
            continue
            
        if not pat_token:
            print("Error: PAT token is required for Confluence access.")
            continue
            
        # Basic validation - PAT tokens are typically long alphanumeric strings
        if len(pat_token) < 10:
            print("Warning: PAT token seems too short. Please verify you copied the complete token.")
            confirm = input("Do you want to proceed with this token? (yes/no): ").lower().strip()
            if confirm not in ['yes', 'y']:
                continue
                
        return pat_token

def export_confluence_to_text(documents, base_url):
    """
    Export Confluence documents to individual text files.
    
    Args:
        documents: List of Document objects from Confluence
        base_url: The original Confluence URL for reference
    """
    # Create output directory
    output_dir = "confluence_export"
    os.makedirs(output_dir, exist_ok=True)
    
    # Summary information for all documents
    summary_info = []
    summary_info.append(f"Confluence Export Summary")
    summary_info.append(f"Base URL: {base_url}")
    summary_info.append(f"Export Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    summary_info.append(f"Total Documents: {len(documents)}")
    summary_info.append(f"Parser: Combined (Default + Enhanced Table Parsing)")
    summary_info.append("=" * 60)
    summary_info.append("")
    
    print(f"Exporting {len(documents)} Confluence documents to text files...")
    
    for i, doc in enumerate(documents, 1):
        try:
            # Extract metadata
            meta = doc.meta if hasattr(doc, 'meta') and doc.meta else {}
            title = meta.get('title', f'Document_{i}')
            page_url = meta.get('url', 'Unknown URL')
            page_id = meta.get('id', 'unknown_id')
            parsing_method = meta.get('parsing_method', 'unknown')
            
            # Clean title for filename (remove invalid characters)
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')
            if not safe_title:
                safe_title = f'Document_{i}'
            
            # Create filename
            filename = f"{i:03d}_{safe_title}_{page_id}.txt"
            filepath = os.path.join(output_dir, filename)
            
            # Write document content to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Title: {title}\n")
                f.write(f"Page ID: {page_id}\n")
                f.write(f"URL: {page_url}\n")
                f.write(f"Parsing Method: {parsing_method}\n")
                f.write(f"Export Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                # Write the actual content
                content = doc.content if hasattr(doc, 'content') else str(doc)
                f.write(content)
            
            # Add to summary
            summary_info.append(f"{i:3d}. {title}")
            summary_info.append(f"     File: {filename}")
            summary_info.append(f"     URL:  {page_url}")
            summary_info.append(f"     Parsing: {parsing_method}")
            summary_info.append(f"     Size: {len(content):,} characters")
            summary_info.append("")
            
            print(f"  Exported: {filename} (parsed using {parsing_method})")
            
        except Exception as e:
            error_msg = f"Error exporting document {i}: {e}"
            print(f"  {error_msg}")
            summary_info.append(f"{i:3d}. ERROR: {error_msg}")
            summary_info.append("")
    
    # Write summary file
    summary_file = os.path.join(output_dir, "export_summary.txt")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(summary_info))
    
    print(f"\nExport completed! Files saved to '{output_dir}' directory:")
    print(f"  - {len(documents)} individual document files")
    print(f"  - 1 summary file: export_summary.txt")
    print(f"  - Total directory: {output_dir}/")
    print(f"  - Enhanced table parsing for merged cells included")

@component
class QueryRewriter:
    """A component that rewrites and enhances queries for better RAG performance."""
    
    def __init__(self, model="HWT-mixtral-8x22b-latest"):
        self.model = model
        # Use HWTGenerator for AFM models, but for chat models we might need different handling
        if model.startswith("aws:anthropic") or model.startswith("gemini"):
            self.generator = HWTGenerator(model="HWT-mixtral-8x22b-latest")  # Fallback to working model
        else:
            self.generator = HWTGenerator(model=model)
    
    @component.output_types(rewritten_query=str)
    def run(self, query: str, chat_history: list = None):
        """Rewrite the query to make it more effective for RAG retrieval."""
        
        # Create the query rewriter prompt
        prompt_template = """You are a query rewriter who extract and refine the query (optional. only when necessary) from the Last Message
First, focus on the Last Message to extract the true query that you are asked to answer
Then, refer to the chat history and refine the query only when necessary. The allowed actions are:
1. if the extracted query is not a question, paraphrase it to a question like "What is the definition of megaflow?"

"""
        
        if chat_history:
            prompt_template += "Chat History:\n"
            for i, (user_msg, assistant_msg) in enumerate(chat_history[-3:]):  # Only last 3 exchanges
                prompt_template += f"User: {user_msg}\n"
                prompt_template += f"Assistant: {assistant_msg}\n"
            prompt_template += "\n"
        
        prompt_template += f"Last Message: {query}\n"
        prompt_template += "Only the rewritten query should be outputed. Do not output anything else."
        
        try:
            result = self.generator.run(prompt=prompt_template)
            if result and "replies" in result and result["replies"]:
                rewritten_query = result["replies"][0].strip()
                # If the rewriter didn't change much or failed, use original
                if len(rewritten_query) < 5 or rewritten_query.lower().startswith("i cannot") or rewritten_query.lower().startswith("error"):
                    return {"rewritten_query": query}
                return {"rewritten_query": rewritten_query}
            else:
                return {"rewritten_query": query}
        except Exception as e:
            print(f"Query rewriter error: {e}. Using original query.")
            return {"rewritten_query": query}

@component
class TextCondenser:
    """A component that condenses text queries to be more concise and focused for retrieval."""
    
    def __init__(self, model="HWT-mixtral-8x22b-latest"):
        self.model = model
        # Use HWTGenerator for AFM models, but for chat models we might need different handling
        if model.startswith("aws:anthropic") or model.startswith("gemini"):
            self.generator = HWTGenerator(model="HWT-mixtral-8x22b-latest")  # Fallback to working model
        else:
            self.generator = HWTGenerator(model=model)
    
    @component.output_types(condensed_query=str)
    def run(self, rewritten_query: str):
        """Condense the query to make it more concise and focused."""
        
        # Create the text condenser prompt based on pipeline.txt
        prompt_template = """For the following question, rephrase it in a concise manner using fewer than 200 words,
while preserving the original meaning and intent.
Output only a single rephrased question without markdown and no extra new lines or spaces.

Question: {query}
Answer:""".format(query=rewritten_query)
        
        try:
            result = self.generator.run(prompt=prompt_template)
            if result and "replies" in result and result["replies"]:
                condensed_query = result["replies"][0].strip()
                # If the condenser didn't work properly or failed, use original
                if len(condensed_query) < 5 or condensed_query.lower().startswith("i cannot") or condensed_query.lower().startswith("error"):
                    return {"condensed_query": rewritten_query}
                return {"condensed_query": condensed_query}
            else:
                return {"condensed_query": rewritten_query}
        except Exception as e:
            print(f"Text condenser error: {e}. Using original query.")
            return {"condensed_query": rewritten_query}

# Define a component to convert a string prompt into a list of ChatMessage objects
@component
class StringToChatMessages:
    """Converts a string prompt into a list of ChatMessage objects."""
    @component.output_types(messages=list[ChatMessage])
    def run(self, prompt: str):
        """Run the component."""
        return {"messages": [ChatMessage.from_user(prompt)]}

@component
class ReplyToCode:
    """
    A component to convert the output of a generator (a list of replies)
    into a single code string, stripping any markdown code blocks.
    """
    @component.output_types(code=str)
    def run(self, replies: list[str]):
        """Strips markdown from the generated code."""
        if replies:
            code = replies[0]
            if code.strip().startswith("```python"):
                code = code.strip()[9:-3].strip()
            elif code.strip().startswith("```"):
                code = code.strip()[3:-3].strip()
            return {"code": code}
        return {"code": ""}


@component
class CodeCleaner:
    """
    A component to clean the output of a CodeGenerator by stripping
    any markdown code blocks and leading natural language text.
    It expects a single code string.
    """
    @component.output_types(code=str)
    def run(self, code: str):
        """Strips markdown and preamble from the generated code string."""
        if not code:
            return {"code": ""}

        cleaned_code = code
        if cleaned_code.strip().startswith("```python"):
            cleaned_code = cleaned_code.strip()[9:-3].strip()
        elif cleaned_code.strip().startswith("```"):
            cleaned_code = cleaned_code.strip()[3:-3].strip()

        lines = cleaned_code.split('\n')

        # Find the first line that is likely code
        first_code_line_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # If it looks like an import, a function/class definition, or a comment, it's code.
            if stripped.startswith(('import ', 'from ', 'def ', 'class ', '#')):
                first_code_line_index = i
                break

        cleaned_code = '\n'.join(lines[first_code_line_index:])

        return {"code": cleaned_code}


class LoadingSpinner:
    """Analysis loading spinner"""

    def __init__(self, message="Processing"):
        self.message = message
        self.running = False
        self.thread = None

    def _spin(self):
        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        # chars = "|/-\\"  # Alternative simple spinner
        i = 0
        while self.running:
            sys.stdout.write(f"\r{chars[i % len(chars)]} {self.message}...")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()


def run_rag_application():
    """Runs the RAG application, allowing users to interact with a RAG pipeline."""
    # --- SHARED SETUP ---
    # Get user input for model selection
    print("Please choose a model:")
    print("1: AFM")  # Use the AFM model
    print("2: Claude Sonnet (Chat)")  # Use the Claude Sonnet model for chat
    print("3: Genie (Chat)")  # Use the Genie (Gemini) model for chat
    model_choice = input("Enter the number of your choice: ")

    # Ask user if they want to clear the document store with proper validation
    while True:
        clear_store = input("Do you want to clear the existing document store? (yes/no): ").lower().strip()
        
        if clear_store in ['yes', 'y']:
            if os.path.exists("../qdrant_storage"):
                shutil.rmtree("../qdrant_storage")
                print("Document store has been cleared.")
            else:
                print("No existing document store found to clear.")
            break
        elif clear_store in ['no', 'n']:
            print("Document store will be preserved.")
            break
        else:
            print("Error: Invalid input. Please enter 'yes' or 'no' (or 'y'/'n').")
            continue

    # Get user input for file type and data source
    while True:
        file_type = input("Are you providing TXT, CSV, PDF files, or Confluence pages? (txt/csv/pdf/confluence): ").lower()
        if file_type not in ['txt', 'csv', 'pdf', 'confluence']:
            print("Invalid file type. Please enter 'txt', 'csv', 'pdf', or 'confluence'.")
            continue

        if file_type == 'confluence':
            # Handle Confluence input separately
            break
        else:
            folder_path = input("Please enter the path to the folder containing your files: ")
            if not os.path.isdir(folder_path):
                print("Invalid folder path. Please try again.")
                continue

            if file_type == 'csv':
                files = glob.glob(os.path.join(folder_path, '*.csv'))
            elif file_type == 'pdf':
                files = glob.glob(os.path.join(folder_path, '*.pdf'))
            else:
                files = glob.glob(os.path.join(folder_path, '*.txt'))

            if not files:
                print(f"No .{file_type} files found in the specified folder. Please provide another folder.")
                continue

            print(f"Found {len(files)} .{file_type} files to process:")
            for f in files:
                print(f"- {f}")

            break

    # Initialize lists and dataframes
    documents = []
    dataframe = pd.DataFrame()

    # Process files based on their type
    if file_type == 'csv':
        all_dfs = []
        for file_path in files:
            try:
                df = pd.read_csv(file_path)
                all_dfs.append(df)
                for index, row in df.iterrows():
                    content = row.to_json()
                    documents.append(Document(content=content))
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        if all_dfs:
            dataframe = pd.concat(all_dfs, ignore_index=True)

        # Initialize the document store and indexing pipeline
        document_store = QdrantDocumentStore(
            path="../qdrant_storage",
            index="getting_started",
            embedding_dim=768,
            force_disable_check_same_thread=True
        )
        indexing_pipeline = Pipeline()
        doc_cleaner = DocumentCleaner(remove_empty_lines=True, remove_extra_whitespaces=True)
        doc_embedder = HWTDocumentEmbedder(model="text-embedding-002")
        doc_writer = DocumentWriter(document_store=document_store)
        indexing_pipeline.add_component("doc_cleaner", doc_cleaner)
        indexing_pipeline.add_component("doc_embedder", doc_embedder)
        indexing_pipeline.add_component("doc_writer", doc_writer)
        indexing_pipeline.connect('doc_cleaner.documents', 'doc_embedder.documents')
        indexing_pipeline.connect('doc_embedder.documents', 'doc_writer.documents')
        indexing_pipeline.run({"doc_cleaner": {"documents": documents}})
        print("CSV data has been indexed.")

    elif file_type == 'txt' or file_type == 'pdf':
        if file_type == 'pdf':
            output_dir = "pdf_output"
            for file_path in files:
                print(f"Parsing {file_path}...")
                manifest = parse_pdf(file_path, output_dir)
                # For now, we only handle the text files from the manifest
                for page, content in manifest.items():
                    if "text" in content:
                        try:
                            with open(content["text"], 'r', encoding='utf-8') as f:
                                text_content = f.read()
                                documents.append(Document(content=text_content, meta={"source": content["text"]}))
                        except Exception as e:
                            print(f"Error reading {content['text']}: {e}")
        else: # txt
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        documents.append(Document(content=content))
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        # Initialize the document store and indexing pipeline for text files
        document_store = QdrantDocumentStore(
            path="../qdrant_storage",
            index="getting_started",
            embedding_dim=768,
            force_disable_check_same_thread=True
        )
        indexing_pipeline = Pipeline()
        doc_cleaner = DocumentCleaner(remove_empty_lines=True, remove_extra_whitespaces=True)
        doc_splitter = DocumentSplitter(split_by="word", split_length=256, split_overlap=0)
        doc_embedder = HWTDocumentEmbedder(model="text-embedding-002")
        doc_writer = DocumentWriter(document_store=document_store)
        indexing_pipeline.add_component("doc_cleaner", doc_cleaner)
        indexing_pipeline.add_component("doc_splitter", doc_splitter)
        indexing_pipeline.add_component("doc_embedder", doc_embedder)
        indexing_pipeline.add_component("doc_writer", doc_writer)
        indexing_pipeline.connect('doc_cleaner.documents', 'doc_splitter.documents')
        indexing_pipeline.connect('doc_splitter.documents', 'doc_embedder.documents')
        indexing_pipeline.connect('doc_embedder.documents', 'doc_writer.documents')
        indexing_result = indexing_pipeline.run({"doc_cleaner": {"documents": documents}})
        print("Text data has been indexed.")
        #print("Indexing Result:")
        #print(indexing_result)

    elif file_type == 'confluence':
        # Handle Confluence pages
        print("Setting up Confluence integration...")
        
        # Get and validate Confluence URL
        confluence_url = get_confluence_url()
        
        # Get authentication token with help option
        pat_token = get_confluence_pat_token()
        
        # Get collection and doc category info
        #collection = input("Enter collection name (default: 'confluence-docs'): ") or "confluence-docs"
        #doc_category = input("Enter document category (default: 'knowledge-base'): ") or "knowledge-base"
        
        # Get hierarchy depth with clear options
        print("\nChoose hierarchy depth for Confluence content retrieval:")
        print("  1 (default): Only the current page")
        print("  2: Current page + immediate children")
        print("  3: Current page + children + grandchildren")
        print("  0: Current page + ALL descendants (complete tree)")
        print()
        
        try:
            hierarchy_input = input("Enter hierarchy depth (0-3, default: 1): ").strip()
            if not hierarchy_input:
                hierarchy = 1
            else:
                hierarchy = int(hierarchy_input)
                if hierarchy not in [0, 1, 2, 3]:
                    print("Invalid hierarchy level. Using default (1).")
                    hierarchy = 1
        except ValueError:
            print("Invalid input. Using default hierarchy level (1).")
            hierarchy = 1
        
        # Set the environment variable for the PAT token
        os.environ['confluence_pat_token'] = pat_token
        
        try:
            # Initialize Confluence components
            confluence_fetcher = ConfluenceFetcher(
                confluence_pat_token=Secret.from_env_var("confluence_pat_token"),
                #collection=collection,
                doc_type="confluence",
                #doc_category=doc_category
            )
            
            # Use our combined parser that integrates both default and enhanced parsing
            combined_parser = CombinedConfluenceParser()
            
            # Create the Confluence pipeline
            confluence_pipeline = Pipeline()
            confluence_pipeline.add_component(name="confluence_fetcher", instance=confluence_fetcher)
            confluence_pipeline.add_component(name="combined_parser", instance=combined_parser)
            confluence_pipeline.connect(sender="confluence_fetcher.pages", receiver="combined_parser.pages")
            
            print(f"Fetching Confluence pages from: {confluence_url}")
            print(f"Hierarchy depth: {hierarchy}")
            
            # Run the Confluence pipeline
            confluence_result = confluence_pipeline.run({
                "confluence_fetcher": {
                    "url": {
                        "page_url": confluence_url,
                        "hierarchy": hierarchy,
                        "ignore_current": False
                    }
                }
            })
            
            # Extract documents from Confluence result
            if "combined_parser" in confluence_result and "documents" in confluence_result["combined_parser"]:
                confluence_documents = confluence_result["combined_parser"]["documents"]
                print(f"Successfully fetched and parsed {len(confluence_documents)} Confluence documents using combined parsing (default + enhanced tables).")
                
                # Export Confluence documents to text files
                #export_confluence_to_text(confluence_documents, confluence_url)
                
                # Initialize the document store and indexing pipeline for Confluence
                document_store = QdrantDocumentStore(
                    path="../qdrant_storage",
                    index="getting_started",
                    embedding_dim=768,
                    force_disable_check_same_thread=True
                )
                indexing_pipeline = Pipeline()
                doc_cleaner = DocumentCleaner(remove_empty_lines=True, remove_extra_whitespaces=True)
                doc_splitter = DocumentSplitter(split_by="word", split_length=256, split_overlap=0)
                doc_embedder = HWTDocumentEmbedder(model="text-embedding-002")
                doc_writer = DocumentWriter(document_store=document_store)
                indexing_pipeline.add_component("doc_cleaner", doc_cleaner)
                indexing_pipeline.add_component("doc_splitter", doc_splitter)
                indexing_pipeline.add_component("doc_embedder", doc_embedder)
                indexing_pipeline.add_component("doc_writer", doc_writer)
                indexing_pipeline.connect('doc_cleaner.documents', 'doc_splitter.documents')
                indexing_pipeline.connect('doc_splitter.documents', 'doc_embedder.documents')
                indexing_pipeline.connect('doc_embedder.documents', 'doc_writer.documents')
                indexing_result = indexing_pipeline.run({"doc_cleaner": {"documents": confluence_documents}})
                print("Confluence data has been indexed.")
                #print("Indexing Result:")
                #print(indexing_result)
                
                # Set documents for potential use in analysis
                documents = confluence_documents
            else:
                print("Error: No documents were fetched from Confluence.")
                return
                
        except Exception as e:
            print(f"Error processing Confluence data: {e}")
            return

    # --- CONDITIONAL PIPELINE AND LOOP ---
    # Conditional pipeline and loop based on model choice
    if model_choice == "2":
        # Claude Sonnet (Chat) model pipeline with query rewriter, text condenser, and similarity ranker
        print("Using Claude Sonnet (Chat) model with Query Rewriter, Text Condenser, and Similarity Ranker.")
        pipeline = Pipeline()
        query_rewriter = QueryRewriter(model="HWT-mixtral-8x22b-latest")
        text_condenser = TextCondenser(model="HWT-mixtral-8x22b-latest")
        text_embedder = HWTTextEmbedder(model="text-embedding-002")
        doc_retriever = QdrantEmbeddingRetriever(document_store=document_store, top_k=TOP_K_RETRIEVAL)
        similarity_ranker = HWTSimilarityRanker(top_k=TOP_K_SIMILARITY)
        prompt_template = """Summarize the retrieved information to answer the user query, relying solely on the retrieved information instead of your inner knowledge
Your audience is an expert, so be highly specific, direct, and concise. If there are ambiguous terms or acronyms, first define them.
When the retrieved information is directly irrelevant, do not guess. You should output "<REJECT> No relevant information" and summarize the retrieved documents to explain the irrelevance
Retrieved information (with relevance scores):
{% for document in documents %}
  Content : {{ document.content }}
  Score : {{ document.score }}
{% endfor %}

User Query: {{query}}
Your Answer:"""
        prompt_builder = PromptBuilder(template=prompt_template)
        string_to_chat = StringToChatMessages()
        chat_generator = AppleGenAIChatGenerator(model="aws:anthropic.claude-sonnet-4-20250514-v1:0")
        answer_builder = AnswerBuilder()
        pipeline.add_component("query_rewriter", query_rewriter)
        pipeline.add_component("text_condenser", text_condenser)
        pipeline.add_component("text_embedder", text_embedder)
        pipeline.add_component("doc_retriever", doc_retriever)
        pipeline.add_component("similarity_ranker", similarity_ranker)
        pipeline.add_component("prompt_builder", prompt_builder)
        pipeline.add_component("string_to_chat", string_to_chat)
        pipeline.add_component("chat_generator", chat_generator)
        pipeline.add_component("answer_builder", answer_builder)
        pipeline.connect("query_rewriter.rewritten_query", "text_condenser.rewritten_query")
        pipeline.connect("text_condenser.condensed_query", "text_embedder.text")
        pipeline.connect("text_embedder.embedding", "doc_retriever.query_embedding")
        pipeline.connect("doc_retriever.documents", "similarity_ranker.documents")
        pipeline.connect("similarity_ranker.documents", "prompt_builder.documents")
        pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
        pipeline.connect("string_to_chat.messages", "chat_generator.messages")
        pipeline.connect("similarity_ranker.documents", "answer_builder.documents")
        pipeline.connect("chat_generator.replies", "answer_builder.replies")
        chat_history = []
        #indexing_pipeline.draw('indexing_pipeline.png')
        #pipeline.draw('pipeline.png')
        while True:
            query = input("Please enter your question (or type 'exit' to quit): ")
            if query.lower() in ['exit', 'quit']:
                break
            if not query:
                continue

            analysis_keywords = ["plot", "chart", "histogram", "graph", "analyze"]
            if model_choice == "2" and file_type == 'csv' and any(keyword in query.lower() for keyword in analysis_keywords):
                run_data_analysis_for_rag(query, dataframe)
                continue

            spinner = LoadingSpinner("Thinking")
            spinner.start()
            result = pipeline.run({
                "query_rewriter": {"query": query, "chat_history": chat_history},
                "similarity_ranker": {"query": query},
                "prompt_builder": {"query": query},
                "answer_builder": {"query": query}
            })
            spinner.stop()
            answer_obj = result['answer_builder']['answers'][0]
            answer = answer_obj.data
            print("\nAnswer:")
            print(answer)
            chat_history.append((query, answer))

    elif model_choice == "3":
        # Genie (Chat) model pipeline with query rewriter, text condenser, and similarity ranker
        print("Using Gemini model with Query Rewriter, Text Condenser, and Similarity Ranker.")
        pipeline = Pipeline()
        query_rewriter = QueryRewriter(model="HWT-mixtral-8x22b-latest")
        text_condenser = TextCondenser(model="HWT-mixtral-8x22b-latest")
        text_embedder = HWTTextEmbedder(model="text-embedding-002")
        doc_retriever = QdrantEmbeddingRetriever(document_store=document_store, top_k=TOP_K_RETRIEVAL)
        similarity_ranker = HWTSimilarityRanker(top_k=TOP_K_SIMILARITY)
        prompt_template = """Summarize the retrieved information to answer the user query, relying solely on the retrieved information instead of your inner knowledge
Your audience is an expert, so be highly specific, direct, and concise. If there are ambiguous terms or acronyms, first define them.
When the retrieved information is directly irrelevant, do not guess. You should output "<REJECT> No relevant information" and summarize the retrieved documents to explain the irrelevance
Retrieved information (with relevance scores):
{% for document in documents %}
  Content : {{ document.content }}
  Score : {{ document.score }}
{% endfor %}

User Query: {{query}}
Your Answer:"""
        prompt_builder = PromptBuilder(template=prompt_template)
        string_to_chat = StringToChatMessages()
        chat_generator = AppleGenAIGeminiChatGenerator(model="gemini-2.5-flash")
        answer_builder = AnswerBuilder()
        pipeline.add_component("query_rewriter", query_rewriter)
        pipeline.add_component("text_condenser", text_condenser)
        pipeline.add_component("text_embedder", text_embedder)
        pipeline.add_component("doc_retriever", doc_retriever)
        pipeline.add_component("similarity_ranker", similarity_ranker)
        pipeline.add_component("prompt_builder", prompt_builder)
        pipeline.add_component("string_to_chat", string_to_chat)
        pipeline.add_component("chat_generator", chat_generator)
        pipeline.add_component("answer_builder", answer_builder)
        pipeline.connect("query_rewriter.rewritten_query", "text_condenser.rewritten_query")
        pipeline.connect("text_condenser.condensed_query", "text_embedder.text")
        pipeline.connect("text_embedder.embedding", "doc_retriever.query_embedding")
        pipeline.connect("doc_retriever.documents", "similarity_ranker.documents")
        pipeline.connect("similarity_ranker.documents", "prompt_builder.documents")
        pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
        pipeline.connect("string_to_chat.messages", "chat_generator.messages")
        pipeline.connect("similarity_ranker.documents", "answer_builder.documents")
        pipeline.connect("chat_generator.replies", "answer_builder.replies")
        chat_history = []
        while True:
            query = input("Please enter your question (or type 'exit' to quit): ")
            if query.lower() in ['exit', 'quit']:
                break
            if not query:
                continue

            analysis_keywords = ["plot", "chart", "histogram", "graph", "analyze"]
            if model_choice == "3" and file_type == 'csv' and any(keyword in query.lower() for keyword in analysis_keywords):
                run_data_analysis_for_rag(query, dataframe)
                continue

            spinner = LoadingSpinner("Thinking")
            spinner.start()
            result = pipeline.run({
                "query_rewriter": {"query": query, "chat_history": chat_history},
                "similarity_ranker": {"query": query},
                "prompt_builder": {"query": query},
                "answer_builder": {"query": query}
            })
            spinner.stop()
            answer_obj = result['answer_builder']['answers'][0]
            answer = answer_obj.data
            print("\nAnswer:")
            print(answer)
            chat_history.append((query, answer))

    else:
        # AFM model pipeline with query rewriter, text condenser, and similarity ranker
        print("Using AFM model with Query Rewriter, Text Condenser, and Similarity Ranker.")
        query_pipeline = Pipeline()
        query_rewriter = QueryRewriter(model="HWT-mixtral-8x22b-latest")
        text_condenser = TextCondenser(model="HWT-mixtral-8x22b-latest")
        doc_retriever = QdrantEmbeddingRetriever(document_store=document_store, top_k=TOP_K_RETRIEVAL)
        text_embedder = HWTTextEmbedder(model="text-embedding-002")
        similarity_ranker = HWTSimilarityRanker(top_k=TOP_K_SIMILARITY)
        prompt_template = """Summarize the retrieved information to answer the user query, relying solely on the retrieved information instead of your inner knowledge
Your audience is an expert, so be highly specific, direct, and concise. If there are ambiguous terms or acronyms, first define them.
When the retrieved information is directly irrelevant, do not guess. You should output "<REJECT> No relevant information" and summarize the retrieved documents to explain the irrelevance
Retrieved information (with relevance scores):
{% for document in documents %}
  Content : {{ document.content }}
  Score : {{ document.score }}
{% endfor %}

User Query: {{query}}
Your Answer:"""
        prompt_builder = PromptBuilder(template=prompt_template)
        generator = HWTGenerator(model="afm-text-30b-instruct-latest")
        query_pipeline.add_component("query_rewriter", query_rewriter)
        query_pipeline.add_component("text_condenser", text_condenser)
        query_pipeline.add_component("text_embedder", text_embedder)
        query_pipeline.add_component("doc_retriever", doc_retriever)
        query_pipeline.add_component("similarity_ranker", similarity_ranker)
        query_pipeline.add_component("prompt_builder", prompt_builder)
        query_pipeline.add_component("generator", generator)
        query_pipeline.connect("query_rewriter.rewritten_query", "text_condenser.rewritten_query")
        query_pipeline.connect("text_condenser.condensed_query", "text_embedder.text")
        query_pipeline.connect("text_embedder.embedding", "doc_retriever.query_embedding")
        query_pipeline.connect("doc_retriever.documents", "similarity_ranker.documents")
        query_pipeline.connect("similarity_ranker.documents", "prompt_builder.documents")
        query_pipeline.connect("prompt_builder.prompt", "generator.prompt")
        chat_history = []
        while True:
            q = input("Please enter your question (or type 'exit' to quit): ")
            if q.lower() in ['exit', 'quit']:
                break
            spinner = LoadingSpinner("Thinking")
            spinner.start()
            query_result = query_pipeline.run({
                "query_rewriter": {"query": q, "chat_history": chat_history},
                "similarity_ranker": {"query": q},
                "prompt_builder": {"query": q}
            })
            spinner.stop()
            if "generator" in query_result and "replies" in query_result["generator"]:
                answer = query_result["generator"]["replies"][0]
                print("\nAnswer:")
                print(answer)
                chat_history.append((q, answer))
            else:
                print("\nCould not find an answer in the query result:")
                print(query_result)

def run_data_analysis_for_rag(user_question: str, dataframe: pd.DataFrame):
    """
    Runs the data analysis pipeline for a given question and dataframe.
    This is intended to be called from the RAG agent.
    """
    if dataframe.empty:
        print("\nNo data available to analyze. Please load a CSV file first.")
        return

    # 1. Save the dataframe to a temporary file
    temp_dir = "output"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, "rag_analysis_data.csv")
    dataframe.to_csv(temp_file_path, index=False)

    files_dict = {"rag_data": temp_file_path}
    print("\nSwitching to Data Analysis mode...")

    # 2. Create and configure the pipeline (using Claude Sonnet)
    pipeline = Pipeline()

    dataset = Dataset()

    custom_system_prompt = (
        "You are a data analysis agent. Your task is to analyze the provided dataset based on the user's query. "
        "When the user asks to filter data, be flexible with your matching. For example, if the user asks for 'ELK4-24', "
        "you should also consider values like 'ELK4-24_Skip' or 'ELK4-24_Clamp' as valid matches. "
        "Generate Python code to perform the analysis and create plots as requested."
    )
    prompt_generator = DataAnalysisPromptGenerator(use_chat_prompt=True,custom_system_prompt=custom_system_prompt)
    code_executor = CodeExecutor(show_code=True)
    exporter = ResultsExporter()
    model_name = "aws:anthropic.claude-sonnet-4-20250514-v1:0"
    code_generator = CodeGenerator(use_chat_model=True, model=model_name)

    pipeline.add_component("dataset", dataset)
    pipeline.add_component("prompt_generator", prompt_generator)
    pipeline.add_component("code_generator", code_generator)
    pipeline.add_component("code_cleaner", CodeCleaner())
    pipeline.add_component("code_executor", code_executor)
    pipeline.add_component("results_exporter", exporter)

    pipeline.connect("dataset.dataframes", "prompt_generator.dataframes")
    pipeline.connect("dataset.schema", "prompt_generator.schema")
    pipeline.connect("prompt_generator.prompt", "code_generator.prompt")
    pipeline.connect("code_generator.code", "code_cleaner.code")
    pipeline.connect("code_cleaner.code", "code_executor.code")
    pipeline.connect("dataset.dataframes", "code_executor.dataframes")
    pipeline.connect("code_cleaner.code", "results_exporter.generated_code")
    pipeline.connect("dataset.dataframes", "results_exporter.dataframes")
    pipeline.connect("code_executor.results", "results_exporter.execution_results")
    pipeline.connect("code_executor.execution_info", "results_exporter.execution_info")
    pipeline.connect("code_executor.code_analysis", "results_exporter.code_analysis")
    pipeline.connect("dataset.dataframes", "code_generator.dataframes")


    # 3. Run the pipeline
    spinner = LoadingSpinner(f"Analyzing your request: '{user_question}'")
    spinner.start()
    start_time = time.time()
    response = pipeline.run(data={
        "dataset": {"files": files_dict},
        "prompt_generator": {"user_prompt": user_question}
    })
    end_time = time.time()
    spinner.stop()

    # 4. Process and display results
    results_exporter_output = response.get("results_exporter", {})
    messages = results_exporter_output.get("messages", [])
    exported_files = results_exporter_output.get("exported_files", [])

    # Show results
    display_results(response, end_time - start_time)

    if exported_files:
        print(f"\nGenerated {len(exported_files)} artifact(s). Opening now...")
        for file_path in exported_files:
            try:
                uri = pathlib.Path(file_path).resolve().as_uri()
                print(f"Opening artifact: {uri}")
                webbrowser.open(uri)
            except Exception as e:
                print(f"Could not open artifact {file_path}: {e}")

    interactive_options(
        response["results_exporter"].get("shared_context", {}),
        response["results_exporter"].get("messages", [])
    )

    # Clean up the temporary file
    os.remove(temp_file_path)


def run_data_analysis():
    """Main function to run the interactive data analysis loop."""

    # 1. Get folder path from user
    while True:
        folder_path = input("Please enter the path to the folder containing your CSV files: ")
        if os.path.isdir(folder_path):
            if not glob.glob(os.path.join(folder_path, '*.csv')):
                print("❌ No CSV files found in the specified folder. Please provide another folder.")
                continue
            break
        else:
            print("❌ Invalid folder path. Please try again.")

    # Create a dictionary of file paths for the Dataset component
    files_dict = {pathlib.Path(f).stem.replace(" ", "_").replace("-", "_"): f for f in glob.glob(os.path.join(folder_path, '*.csv'))}
    print(f"✅ Loaded {len(files_dict)} CSV files from '{folder_path}'.")
    print("\nDataframes will be loaded with the following names:")
    for name in files_dict.keys():
        print(f"- {name}")

    # 2. Get model choice from user
    print("\nPlease choose a model for data analysis:")
    print("1: Claude Sonnet")
    print("2: Genie (Gemini)")
    model_choice = input("Enter the number of your choice: ")

    # 3. Create and configure the pipeline
    pipeline = Pipeline()

    # Initialize components
    dataset = Dataset()
    prompt_generator = DataAnalysisPromptGenerator()
    code_executor = CodeExecutor(show_code=True)
    exporter = ResultsExporter()

    # Add common components to pipeline
    pipeline.add_component("dataset", dataset)
    pipeline.add_component("prompt_generator", prompt_generator)
    pipeline.add_component("code_executor", code_executor)
    pipeline.add_component("results_exporter", exporter)

    if model_choice == '2': # Gemini
        model_name = "gemini-2.5-flash"
        code_generator = CodeGenerator(model=model_name)
        pipeline.add_component("code_generator", code_generator)
        pipeline.add_component("code_cleaner", CodeCleaner())
        pipeline.connect("prompt_generator.prompt", "code_generator.prompt")
        pipeline.connect("code_generator.code", "code_cleaner.code")
        pipeline.connect("code_cleaner.code", "code_executor.code")
        pipeline.connect("code_cleaner.code", "results_exporter.generated_code")
        pipeline.connect("dataset.dataframes", "code_generator.dataframes")
    else: # Default to Claude
        model_name = "aws:anthropic.claude-sonnet-4-20250514-v1:0"
        code_generator = CodeGenerator(model=model_name)
        pipeline.add_component("code_generator", code_generator)
        pipeline.add_component("code_cleaner", CodeCleaner())
        pipeline.connect("prompt_generator.prompt", "code_generator.prompt")
        pipeline.connect("code_generator.code", "code_cleaner.code")
        pipeline.connect("code_cleaner.code", "code_executor.code")
        pipeline.connect("code_cleaner.code", "results_exporter.generated_code")
        pipeline.connect("dataset.dataframes", "code_generator.dataframes")

    # Define common data flow connections
    pipeline.connect("dataset.dataframes", "prompt_generator.dataframes")
    pipeline.connect("dataset.schema", "prompt_generator.schema")
    pipeline.connect("dataset.dataframes", "code_executor.dataframes")
    pipeline.connect("code_executor.results", "results_exporter.execution_results")
    pipeline.connect("code_executor.execution_info", "results_exporter.execution_info")
    pipeline.connect("code_executor.code_analysis", "results_exporter.code_analysis")
    pipeline.connect("dataset.dataframes", "results_exporter.dataframes")

    # Initial run to load the dataset and provide an overview.
    spinner = LoadingSpinner("Loading dataset and generating initial overview")
    spinner.start()

    initial_question = "For each dataframe, display its .info() and the first 5 rows."

    initial_response = pipeline.run(data={
        "dataset": {"files": files_dict},
        "prompt_generator": {"user_prompt": initial_question}
    })
    spinner.stop()

    messages = initial_response.get("results_exporter", {}).get("messages", [])
    if messages:
        for msg in messages:
            print(f"\n{msg.text}")
    else:
        print("Could not get a dataset overview.")

    print("\n✅ Dataset loaded. You can now ask questions about the data.")
    print("For example: 'Plot a histogram of the age column'.")

    # Start interactive loop
    while True:
        user_question = input("\n> ").strip()
        if user_question.lower() in ['exit', 'quit']:
            print("👋 Exiting analysis session.")
            break

        if not user_question:
            continue

        spinner = LoadingSpinner("🔍 Analyzing your data")
        spinner.start()
        start_time = time.time()
        response = pipeline.run(data={
            "dataset": {"files": files_dict},
            "prompt_generator": {"user_prompt": user_question}
        })
        end_time = time.time()
        spinner.stop()
        print("✅ Analysis complete!")

        # Show results
        display_results(response, end_time - start_time)

        results_exporter_output = response.get("results_exporter", {})
        exported_files = results_exporter_output.get("exported_files", [])

        if exported_files:
            print(f"\nGenerated {len(exported_files)} artifact(s). Opening now...")
            for file_path in exported_files:
                try:
                    uri = pathlib.Path(file_path).resolve().as_uri()
                    print(f"Opening artifact: {uri}")
                    webbrowser.open(uri)
                except Exception as e:
                    print(f"Could not open artifact {file_path}: {e}")

        interactive_options(
            response["results_exporter"].get("shared_context", {}),
            response["results_exporter"].get("messages", [])
        )


def main():
    """Main function to run the application."""
    logo = """
██████╗    █████╗    ██████╗  ██╗  ██╗   █████╗    ██████╗  ██╗ ███╗   ██╗  ██████╗
██╔══██╗  ██╔══██╗  ██╔════╝  ██║ ██╔╝  ██╔══██╗  ██╔════╝  ██║ ████╗  ██║ ██╔════╝
██████╔╝  ███████║  ██║       █████╔╝   ███████║  ██║  ███╗ ██║ ██╔██╗ ██║ ██║  ███╗
██╔═══╝   ██╔══██║  ██║       ██╔═██╗   ██╔══██║  ██║   ██║ ██║ ██║╚██╗██║ ██║   ██║
██║       ██║  ██║  ╚██████╗  ██║  ██╗  ██║  ██║  ╚██████╔╝ ██║ ██║ ╚████║ ╚██████╔╝
╚═╝       ╚═╝  ╚═╝   ╚═════╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝   ╚═════╝  ╚═╝ ╚═╝  ╚═══╝  ╚═════╝

 ██████╗   ███████╗  ███╗   ██║  ██╗  ███████╗
██╔════╝   ██╔════╝  ████╗  ██║  ██║  ██╔════╝
██║  ███╗  █████╗    ██╔██╗ ██║  ██║  █████╗
██║   ██║  ██╔══╝    ██║╚██╗██║  ██║  ██╔══╝
╚██████╔╝  ███████╗  ██║ ╚████║  ██║  ███████╗
 ╚═════╝   ╚══════╝  ╚═╝  ╚═══╝  ╚═╝  ╚══════╝

"""
    print(logo)
    print("Welcome to Genie!")
    # Present the main menu to the user
    print("Please choose an option:")
    print("1: Run RAG Application")
    print("2: Run Data Analysis")
    choice = input("Enter the number of your choice: ")

    # Run the selected application based on user input
    if choice == '1':
        run_rag_application()
    elif choice == '2':
        run_data_analysis()
    else:
        print("Invalid choice. Please run the script again and choose a valid option.")

if __name__ == "__main__":
    main()