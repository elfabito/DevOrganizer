"""
File Processor Module for Dev Project Organizer
Handles file uploads and text extraction from various document formats
"""

import os
import logging
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import PyPDF2
from docx import Document
import markdown2

# Configure logging
logger = logging.getLogger(__name__)

# Allowed file extensions for project documents
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'txt', 'md', 'markdown'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file


def allowed_document_file(filename: str) -> bool:
    """
    Check if a filename has an allowed document extension
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if the file extension is allowed, False otherwise
    """
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_DOCUMENT_EXTENSIONS


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from a PDF file
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    try:
        text_content = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from each page
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text.strip():
                    text_content.append(f"--- Page {page_num + 1} ---\n{text}")
        
        return '\n\n'.join(text_content)
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text content from a DOCX file
    
    Args:
        file_path: Path to the DOCX file
        
    Returns:
        Extracted text content
    """
    try:
        doc = Document(file_path)
        
        text_content = []
        
        # Extract text from paragraphs
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join(cell.text.strip() for cell in row.cells)
                if row_text.strip():
                    text_content.append(row_text)
        
        return '\n\n'.join(text_content)
    
    except Exception as e:
        logger.error(f"Error extracting text from DOCX {file_path}: {str(e)}")
        raise Exception(f"Failed to extract text from DOCX: {str(e)}")


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text content from a TXT file
    
    Args:
        file_path: Path to the TXT file
        
    Returns:
        Extracted text content
    """
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, try with errors='ignore'
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    
    except Exception as e:
        logger.error(f"Error extracting text from TXT {file_path}: {str(e)}")
        raise Exception(f"Failed to extract text from TXT: {str(e)}")


def extract_text_from_markdown(file_path: str) -> str:
    """
    Extract text content from a Markdown file
    Converts markdown to plain text for better AI processing
    
    Args:
        file_path: Path to the Markdown file
        
    Returns:
        Extracted text content (markdown converted to plain text)
    """
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        markdown_content = None
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    markdown_content = file.read()
                    break
            except UnicodeDecodeError:
                continue
        
        if markdown_content is None:
            # If all encodings fail, try with errors='ignore'
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                markdown_content = file.read()
        
        # Convert markdown to HTML, then strip HTML tags for plain text
        html_content = markdown2.markdown(markdown_content)
        
        # Simple HTML tag removal (for basic text extraction)
        import re
        text_content = re.sub(r'<[^>]+>', '', html_content)
        text_content = text_content.replace('&nbsp;', ' ')
        text_content = text_content.replace('&amp;', '&')
        text_content = text_content.replace('&lt;', '<')
        text_content = text_content.replace('&gt;', '>')
        text_content = text_content.replace('&quot;', '"')
        
        return text_content.strip()
    
    except Exception as e:
        logger.error(f"Error extracting text from Markdown {file_path}: {str(e)}")
        raise Exception(f"Failed to extract text from Markdown: {str(e)}")


def extract_text_from_file(file_path: str, filename: str) -> str:
    """
    Extract text from a file based on its extension
    
    Args:
        file_path: Path to the file
        filename: Original filename (for extension detection)
        
    Returns:
        Extracted text content
    """
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    try:
        if extension == 'pdf':
            return extract_text_from_pdf(file_path)
        elif extension == 'docx':
            return extract_text_from_docx(file_path)
        elif extension == 'txt':
            return extract_text_from_txt(file_path)
        elif extension in ['md', 'markdown']:
            return extract_text_from_markdown(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {extension}")
    
    except Exception as e:
        logger.error(f"Error extracting text from file {filename}: {str(e)}")
        raise


def process_uploaded_files(files: List[FileStorage], upload_folder: str) -> Dict[str, any]:
    """
    Process multiple uploaded files and extract their text content
    
    Args:
        files: List of uploaded file objects
        upload_folder: Directory to save uploaded files temporarily
        
    Returns:
        Dictionary containing:
        - 'files': List of processed file info (name, size, type)
        - 'extracted_texts': List of dictionaries with filename and extracted text
        - 'combined_text': All extracted texts combined into one string
        - 'errors': List of any errors encountered
    """
    os.makedirs(upload_folder, exist_ok=True)
    
    result = {
        'files': [],
        'extracted_texts': [],
        'combined_text': '',
        'errors': []
    }
    
    for file in files:
        if not file or not file.filename:
            continue
        
        filename = secure_filename(file.filename)
        
        # Validate file extension
        if not allowed_document_file(filename):
            result['errors'].append(f"File '{filename}' has an unsupported format. Allowed: PDF, DOCX, TXT, MD")
            continue
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            result['errors'].append(f"File '{filename}' exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB")
            continue
        
        try:
            # Save file temporarily
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Extract text
            extracted_text = extract_text_from_file(file_path, filename)
            
            # Store file info
            result['files'].append({
                'name': filename,
                'size': file_size,
                'type': filename.rsplit('.', 1)[1].lower()
            })
            
            # Store extracted text
            result['extracted_texts'].append({
                'filename': filename,
                'text': extracted_text
            })
            
            # Clean up temporary file
            try:
                os.remove(file_path)
            except:
                pass
        
        except Exception as e:
            error_msg = f"Error processing file '{filename}': {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            
            # Try to clean up file if it was saved
            try:
                file_path = os.path.join(upload_folder, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
    
    # Combine all extracted texts
    if result['extracted_texts']:
        combined_parts = []
        for item in result['extracted_texts']:
            combined_parts.append(f"=== Content from: {item['filename']} ===\n\n{item['text']}\n")
        
        result['combined_text'] = '\n\n'.join(combined_parts)
    
    return result


def validate_uploaded_files(files: List[FileStorage]) -> Dict[str, any]:
    """
    Validate uploaded files without processing them
    
    Args:
        files: List of uploaded file objects
        
    Returns:
        Dictionary containing:
        - 'valid': Boolean indicating if all files are valid
        - 'errors': List of validation errors
        - 'file_count': Number of valid files
    """
    result = {
        'valid': True,
        'errors': [],
        'file_count': 0
    }
    
    for file in files:
        if not file or not file.filename:
            continue
        
        filename = secure_filename(file.filename)
        
        # Validate file extension
        if not allowed_document_file(filename):
            result['valid'] = False
            result['errors'].append(
                f"File '{filename}' has an unsupported format. "
                f"Allowed formats: {', '.join(ALLOWED_DOCUMENT_EXTENSIONS).upper()}"
            )
            continue
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            result['valid'] = False
            result['errors'].append(
                f"File '{filename}' exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB"
            )
            continue
        
        result['file_count'] += 1
    
    return result
