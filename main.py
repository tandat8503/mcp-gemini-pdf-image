"""
Gemini PDF Understanding MCP Server
A Model Context Protocol server for understanding PDF documents using Google Gemini API
Optimized for single-request workflow: URL(s) + prompt → result
"""

import logging
import os
import io
import warnings
import json
from typing import Annotated, Optional, Union

import httpx
from google import genai
from google.genai import types
from fastmcp import FastMCP
from pydantic import BaseModel
from dotenv import load_dotenv

# Suppress Pydantic deprecation warnings from FastMCP internal code
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize MCP server
mcp = FastMCP("gemini-pdf")

# API Configuration
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT = None

# Configure Gemini SDK
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# Cache for PDF Part objects to avoid re-downloading same URL
file_cache: dict[str, types.Part] = {}  # url -> Part object

class PDFUnderstandingResult(BaseModel):
    """Result of PDF understanding"""
    success: bool
    content: str
    error: Optional[str] = None
    file_ids: Optional[str] = None  # For reference

def format_response_data(data: dict | list[str] | str, success: bool = True, error: Optional[str] = None) -> dict:
    return {
        "success": success,
        "data": data if success else None,
        "error": error if not success else None,
    }

async def download_pdf_from_url(url: str) -> bytes:
    """Download PDF from URL"""
    logger.info(f"Downloading PDF from: {url}")
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(DEFAULT_TIMEOUT)) as client:
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # Verify content type
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                logger.warning(f"Content-Type is {content_type}, not PDF. Proceeding anyway...")
            
            pdf_data = response.content
            size_mb = len(pdf_data) / (1024 * 1024)
            logger.info(f"Downloaded PDF: {size_mb:.2f} MB")
            
            return pdf_data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading PDF: {e.response.status_code}")
            raise Exception(f"Failed to download PDF: HTTP {e.response.status_code}")
        except httpx.TimeoutException:
            logger.error("Timeout downloading PDF")
            raise Exception("PDF download timeout")
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            raise Exception(f"Failed to download PDF: {str(e)}")


async def get_pdf_part(url: str) -> types.Part:
    """
    Download PDF and create Part object for inline data processing
    Returns Part object ready for generate_content
    """
    # Check cache first
    if url in file_cache:
        logger.info(f"Using cached PDF data for URL: {url}")
        return file_cache[url]
    
    # Download PDF
    pdf_data = await download_pdf_from_url(url)
    
    # Create Part object from bytes (inline data - recommended for PDFs < 20MB)
    logger.info("Creating PDF Part object for inline processing...")
    try:
        pdf_part = types.Part.from_bytes(
            data=pdf_data,
            mime_type='application/pdf'
        )
        
        # Cache for future use
        file_cache[url] = pdf_part
        
        logger.info(f"PDF Part created successfully")
        return pdf_part
        
    except Exception as e:
        logger.error(f"Error creating PDF Part: {str(e)}")
        raise Exception(f"Failed to process PDF: {str(e)}")
@mcp.tool(
    name="analyze_single_pdf",
    description="Use this tool when you need to understand the content of a single PDF from a public URL. It can summarize the document, answer specific questions about its content, or extract key information like names, dates, or figures. The tool will return the generated text analysis as a JSON object."
)
async def analyze_single_pdf(
    pdf_url: Annotated[str, "URL of the PDF file to analyze (must be publicly accessible)"],
    prompt: Annotated[str, "What you want to do with the PDF: summarize, extract key points, answer questions, translate, etc."],
) -> str:
    """Analyze a single PDF from URL with Gemini AI."""
    try:
        logger.info(f"Processing single PDF: {pdf_url}")
        
        # Validate API key
        if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
            return json.dumps(format_response_data("", success=False, error="GEMINI_API_KEY is not configured. Please set it in your .env file. Get key at: https://aistudio.google.com/app/apikey"))
        
        # Get PDF as Part object
        try:
            pdf_part = await get_pdf_part(pdf_url)
        except Exception as e:
            return json.dumps(format_response_data("", success=False, error=f"Error processing PDF ({pdf_url}): {str(e)}"))
        
        # Generate content with PDF
        logger.info(f"Generating content with PDF using model: {DEFAULT_MODEL}")
        try:
            contents = [pdf_part, prompt]
            response = client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=contents
            )
            
            if response.text:
                logger.info("PDF processed successfully")
                payload = {
                    "result": response.text,
                    "note": "Processed 1 PDF with inline data"
                }
                return json.dumps(format_response_data(payload))
            else:
                return json.dumps(format_response_data("", success=False, error="No response generated from Gemini"))
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return json.dumps(format_response_data("", success=False, error=f"Error processing PDF: {str(e)}"))
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return json.dumps(format_response_data("", success=False, error=f"Unexpected error: {str(e)}"))


@mcp.tool(
    name="analyze_multiple_pdfs",
    description="Use this tool to analyze and find insights across multiple PDF documents from a list of public URLs. It is ideal for comparing two or more documents, synthesizing a combined summary, or extracting common themes and differences. The tool returns a single, consolidated text analysis as a JSON object."
)
async def analyze_multiple_pdfs(
    pdf_urls: Annotated[list[str], "List of PDF URLs to analyze (all must be publicly accessible)"],
    prompt: Annotated[str, "What you want to do with the PDFs: compare, find common themes, create combined summary, extract data from all, etc."],
) -> str:
    """Analyze multiple PDFs from URLs with Gemini AI."""
    try:
        logger.info(f"Processing {len(pdf_urls)} PDFs")
        
        # Validate API key
        if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
            return json.dumps(format_response_data("", success=False, error="GEMINI_API_KEY is not configured. Please set it in your .env file. Get key at: https://aistudio.google.com/app/apikey"))
        
        # Get all PDFs as Part objects
        pdf_parts = []
        
        for idx, url in enumerate(pdf_urls, 1):
            logger.info(f"Processing PDF {idx}/{len(pdf_urls)}: {url}")
            try:
                pdf_part = await get_pdf_part(url)
                pdf_parts.append(pdf_part)
            except Exception as e:
                return json.dumps(format_response_data("", success=False, error=f"Error processing PDF {idx} ({url}): {str(e)}"))
        
        # Generate content with PDFs
        logger.info(f"Generating content with {len(pdf_parts)} PDFs using model: {DEFAULT_MODEL}")
        try:
            contents = pdf_parts + [prompt]
            response = client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=contents
            )
            
            if response.text:
                logger.info("PDFs processed successfully")
                payload = {
                    "result": response.text,
                    "note": f"Processed {len(pdf_parts)} PDFs with inline data"
                }
                return json.dumps(format_response_data(payload))
            else:
                return json.dumps(format_response_data("", success=False, error="No response generated from Gemini"))
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return json.dumps(format_response_data("", success=False, error=f"Error processing PDFs: {str(e)}"))
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return json.dumps(format_response_data("", success=False, error=f"Unexpected error: {str(e)}"))


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
