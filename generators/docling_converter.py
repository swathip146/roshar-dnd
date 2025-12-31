"""
Docling Document Converter Utilities
Provides shared DocumentConverter and extraction utilities for PDF, text, and markdown files
"""

import os
import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from io import BytesIO

# Configure logger for this module
logger = logging.getLogger(__name__)

# Docling imports
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc.base import ImageRefMode
from docling_core.types.doc.document import ImageRef, Size

# Data processing imports
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
import pandas as pd  # Only imported for DataFrame operations

# Haystack imports
from haystack import Document

# Advanced filtering available (methods defined below)
ADVANCED_FILTERING_AVAILABLE = True


# Global singleton converter for memory efficiency (saves ~87% memory)
_global_converter: Optional[DocumentConverter] = None


# ============================================================================
# Advanced Image Filtering Utilities (from parser system)
# ============================================================================

def calculate_md5_hash(image_path: str) -> str:
    """
    Calculate MD5 hash for fast byte-level deduplication (Stage 1).

    This is the first stage of two-stage hybrid hashing strategy.
    MD5 is ~50x faster than perceptual hashing and eliminates exact duplicates.

    Args:
        image_path: Path to image file

    Returns:
        MD5 hash string (empty string on error)
    """
    try:
        import hashlib
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"⚠️  Error calculating MD5 for {image_path}: {e}")
        return ""


def calculate_perceptual_hash(img, method: str = 'ahash') -> str:
    """
    Calculate fast perceptual hash from loaded PIL Image (Stage 2).

    Uses lighter algorithms (aHash/dHash) instead of slow pHash (DCT-based).

    Args:
        img: PIL Image object (already loaded)
        method: Hash method - 'ahash' (fastest), 'dhash' (recommended), 'phash' (slow)

    Returns:
        Perceptual hash string (empty string on error)
    """
    try:
        import imagehash

        if method == 'ahash':
            return str(imagehash.average_hash(img))
        elif method == 'dhash':
            return str(imagehash.dhash(img))
        elif method == 'phash':
            return str(imagehash.phash(img))
        else:
            return str(imagehash.average_hash(img))
    except Exception as e:
        logger.warning(f"⚠️  Error calculating perceptual hash: {e}")
        return ""


def is_image_mostly_empty_from_pil(img, threshold: float = 0.1) -> bool:
    """
    Check if image is mostly empty/white using already-loaded PIL Image.

    Args:
        img: PIL Image object (already loaded)
        threshold: Minimum ratio of non-white pixels (default 0.1 = 10%)

    Returns:
        True if image is mostly empty, False otherwise
    """
    try:
        import numpy as np

        if img.mode != 'L':
            img_gray = img.convert('L')
        else:
            img_gray = img

        pixels = np.array(img_gray)
        non_white_ratio = np.sum(pixels < 240) / pixels.size
        return bool(non_white_ratio < threshold)
    except Exception as e:
        logger.warning(f"⚠️  Error checking if image is empty: {e}")
        return False


def filter_images_advanced(
    images: List[Dict],
    temp_dir: Path,
    image_filter_config: Dict[str, Any],
    final_output_dir: Optional[Path] = None
) -> tuple:
    """
    Advanced image filtering with two-stage hybrid hashing strategy.

    Stage 1: MD5 hash for byte-level deduplication (~0.002s/image)
    Stage 2: Perceptual hash for visual similarity (~0.012s/image)

    94% faster than naive perceptual hashing approach.

    Args:
        images: List of image dicts with 'path' and 'index' keys
        temp_dir: Temporary directory containing extracted images
        image_filter_config: Configuration dict with filtering parameters
        final_output_dir: Optional final output directory (copies filtered images)

    Returns:
        Tuple of (filtered_images, dedup_mapping)
        - filtered_images: List of image dicts that passed all filters
        - dedup_mapping: Dict mapping duplicate paths to their kept representatives
    """
    import shutil

    filtered = []
    dedup_mapping = {}

    # Stage 1: MD5 hash tracking for byte-identical duplicates
    md5_hashes = {}

    # Stage 2: Perceptual hash tracking for visual similarity
    seen_phashes = {}

    perceptual_method = image_filter_config.get('perceptual_hash_method', 'dhash')

    for img_data in images:
        img_path = img_data['path']

        try:
            # Fast pre-checks before any image loading
            file_size_mb = os.path.getsize(img_path) / (1024 * 1024)
            if file_size_mb > image_filter_config['max_file_size_mb']:
                logger.debug(f"  Filtered image (too large): {os.path.basename(img_path)}")
                continue

            # Stage 1: MD5 hash for byte-identical duplicates (very fast)
            if image_filter_config['enable_deduplication']:
                md5_hash = calculate_md5_hash(img_path)
                if md5_hash in md5_hashes:
                    kept_image = md5_hashes[md5_hash]
                    dedup_mapping[img_path] = kept_image
                    logger.debug(f"  Filtered image (MD5 duplicate): {os.path.basename(img_path)}")
                    continue
                md5_hashes[md5_hash] = img_path

            # Load image ONCE for all checks (dimension, emptiness, perceptual hash)
            with Image.open(img_path) as img:
                # Check dimensions
                width, height = img.size
                if (width < image_filter_config['min_width'] or
                    height < image_filter_config['min_height']):
                    logger.debug(f"  Filtered image (too small): {os.path.basename(img_path)}")
                    continue

                # Check if mostly empty using already-loaded PIL object (no redundant I/O!)
                if is_image_mostly_empty_from_pil(img, image_filter_config['min_content_ratio']):
                    logger.debug(f"  Filtered image (mostly empty): {os.path.basename(img_path)}")
                    continue

                # Stage 2: Perceptual hash (aHash/dHash) on already-loaded image
                if image_filter_config.get('enable_perceptual_dedup', False):
                    phash = calculate_perceptual_hash(img, method=perceptual_method)
                    if phash in seen_phashes:
                        kept_image = seen_phashes[phash]
                        dedup_mapping[img_path] = kept_image
                        logger.debug(f"  Filtered image ({perceptual_method} duplicate): {os.path.basename(img_path)}")
                        continue
                    seen_phashes[phash] = img_path

            # Image passed all filters
            filtered.append(img_data)

        except Exception as e:
            logger.warning(f"  ⚠️  Error filtering image {os.path.basename(img_path)}: {e}")
            continue

    # If final_output_dir provided, copy filtered images there and update paths
    if final_output_dir:
        final_output_dir.mkdir(parents=True, exist_ok=True)

        for img_data in filtered:
            temp_path = img_data['path']
            final_path = final_output_dir / Path(temp_path).name
            shutil.copy2(temp_path, final_path)
            img_data['original_temp_path'] = temp_path
            img_data['path'] = str(final_path)

    return filtered, dedup_mapping


# ============================================================================
# End of Advanced Image Filtering Utilities
# ============================================================================


def get_or_create_converter(config=None) -> DocumentConverter:
    """
    Get or create a shared DocumentConverter instance

    Memory efficient: Single 200MB instance vs 1.6GB for multiple instances

    Args:
        config: BatchDoclingConfig instance (optional)

    Returns:
        DocumentConverter instance
    """
    global _global_converter

    if _global_converter is None:
        # Default pipeline options if no config provided
        if config is None:
            pipeline_options = PdfPipelineOptions(
                do_ocr=False,
                do_table_structure=True,
                generate_picture_images=True
            )
        else:
            pipeline_options = config.to_pipeline_options()

        # Create converter with PDF format options
        _global_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )

    return _global_converter


def extract_text_from_docling(result, file_path: str, image_mode=None) -> str:
    """
    Extract text content from Docling conversion result

    Args:
        result: Docling ConversionResult
        file_path: Path to source file (for logging)
        image_mode: Optional ImageRefMode for controlling image references in markdown

    Returns:
        Markdown-formatted text content
    """
    try:
        # Export to markdown format with optional image mode
        if image_mode is not None:
            markdown_text = result.document.export_to_markdown(image_mode=image_mode)
        else:
            markdown_text = result.document.export_to_markdown()
        return markdown_text
    except Exception as e:
        logger.warning(f"  ⚠️  Error extracting text from {os.path.basename(file_path)}: {e}")
        # Fallback to plain text
        return result.document.export_to_text() if hasattr(result.document, 'export_to_text') else ""


def extract_tables_from_docling(result, file_path: str, output_dir: str = "./extracted_tables") -> List[Dict[str, Any]]:
    """
    Extract tables from Docling result and save as Parquet files

    Args:
        result: Docling ConversionResult
        file_path: Path to source file
        output_dir: Directory to save Parquet files

    Returns:
        List of table metadata dictionaries
    """
    tables_data = []

    if not hasattr(result.document, 'tables') or not result.document.tables:
        return tables_data

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    file_stem = Path(file_path).stem
    basename = os.path.basename(file_path)

    for i, table in enumerate(result.document.tables):
        try:
            # Export table to DataFrame
            df = table.export_to_dataframe(doc=result.document)

            if df.empty:
                continue

            # Handle duplicate column names by making them unique
            if df.columns.duplicated().any():
                # Create unique column names by appending suffixes
                cols = pd.Series(df.columns)
                for dup in cols[cols.duplicated()].unique():
                    # Find all occurrences of this duplicate
                    indices = [i for i, x in enumerate(cols) if x == dup]
                    # Rename all but the first occurrence
                    for idx, pos in enumerate(indices[1:], start=2):
                        cols.iloc[pos] = f"{dup}_{idx}"
                df.columns = cols.tolist()
                print(f"  ⚠️  Fixed duplicate column names in table {i}")

            # Save as Parquet with compression
            parquet_path = os.path.join(output_dir, f"{file_stem}_table_{i}.parquet")
            pq.write_table(
                pa.Table.from_pandas(df),
                parquet_path,
                compression='zstd'
            )

            # Convert to markdown for embedding
            markdown = df.to_markdown(index=False)

            tables_data.append({
                'parquet_path': parquet_path,
                'markdown': markdown,
                'row_count': len(df),
                'column_count': len(df.columns),
                'table_index': i,
                'source_file': basename
            })

        except Exception as e:
            logger.warning(f"  ⚠️  Error extracting table {i} from {basename}: {e}")
            continue

    return tables_data


def _extract_image_from_figure(figure, output_path: str, doc=None) -> bool:
    """
    Helper function to extract image from Docling figure

    Args:
        figure: Docling picture/figure object
        output_path: Path to save image
        doc: Docling document object (required for get_image() method)

    Returns:
        True if extraction successful, False otherwise
    """
    try:
        # Try to get PIL Image directly
        if hasattr(figure, 'get_image') and callable(figure.get_image):
            # Pass doc if available (required by newer Docling API)
            pil_image = figure.get_image(doc) if doc else figure.get_image()
            if pil_image is not None:
                pil_image.save(output_path, 'PNG')
                return True

        # Try to extract from image attribute
        if hasattr(figure, 'image') and figure.image is not None:
            if isinstance(figure.image, Image.Image):
                figure.image.save(output_path, 'PNG')
                return True

        # Try base64 URI if available
        if hasattr(figure, 'uri') and figure.uri:
            uri = figure.uri
            if uri.startswith('data:image'):
                # Extract base64 data
                base64_data = uri.split(',')[1] if ',' in uri else uri
                image_data = base64.b64decode(base64_data)

                # Create PIL Image and save
                pil_image = Image.open(BytesIO(image_data))
                pil_image.save(output_path, 'PNG')
                return True

        return False

    except Exception as e:
        logger.warning(f"    ⚠️  Image extraction error: {e}")
        return False


def _generate_image_caption(
    image_path: str,
    config
) -> str:
    """
    Generate caption for image using LLM or fallback.

    Centralizes caption generation logic used by both filtering approaches.

    Args:
        image_path: Path to saved image file
        config: BatchDoclingConfig instance

    Returns:
        Caption string (LLM-generated or fallback)
    """
    # Extract image filename without extension
    image_filename = Path(image_path).stem

    # Generate caption (LLM or fallback)
    if config and config.use_llm_captions:
        # Import captioning utility (lazy import)
        from generators.gemini_vision_captioner import caption_image_with_gemini

        # Attempt LLM caption generation
        llm_caption = caption_image_with_gemini(
            image_path=image_path,
            model=config.caption_model,
            custom_prompt=config.caption_prompt,
            timeout=config.caption_timeout
        )

        if llm_caption:
            # Format as: filename_LLM-caption
            return f"Extracted image: {image_filename}, Caption: {llm_caption}"

    # Fallback caption: just the filename
    caption = f"Extracted image: {image_filename} located at {image_path}"
    return caption


def _extract_images_with_basic_filtering(
    result,
    file_path: str,
    output_dir: str,
    min_width: int,
    min_height: int,
    config
) -> tuple:
    """
    Extract images using basic filtering (existing implementation).

    Used as fallback when advanced filtering is not available.

    Args:
        result: Docling ConversionResult
        file_path: Path to source file
        output_dir: Directory to save image files
        min_width: Minimum image width
        min_height: Minimum image height
        config: BatchDoclingConfig instance

    Returns:
        Tuple of (images_data, filtered_paths, dedup_mapping)
        - dedup_mapping is empty dict (no deduplication in basic mode)
    """
    images_data = []
    file_stem = Path(file_path).stem
    basename = os.path.basename(file_path)

    for i, figure in enumerate(result.document.pictures):
        try:
            # Generate output path
            image_path = os.path.join(output_dir, f"{file_stem}_image_{i+1}.png")

            # Try to extract image
            if not _extract_image_from_figure(figure, image_path, result.document):
                continue

            # Apply basic filtering
            with Image.open(image_path) as img:
                width, height = img.size

                # Filter out very small images
                if width < min_width or height < min_height:
                    os.remove(image_path)
                    continue

                # Check if image is mostly blank
                grayscale = img.convert('L')
                extrema = grayscale.getextrema()
                if extrema[0] == extrema[1]:
                    os.remove(image_path)
                    continue

            # Generate caption
            caption = _generate_image_caption(image_path, config)

            # Update picture.image.uri for this specific picture in result.document.pictures
            # Note: We directly update result.document.pictures[i], not figure
            if hasattr(result.document.pictures[i], 'image'):
                if result.document.pictures[i].image is None:
                    # Create new ImageRef if it doesn't exist
                    result.document.pictures[i].image = ImageRef(
                        uri=Path(image_path),
                        mimetype="image/png",
                        dpi=72,
                        size=Size(width=0, height=0)
                    )
                    logger.debug(f"    Created new ImageRef for picture {i+1}: {image_path}")
                elif result.document.pictures[i].image is not None:
                    # Update existing ImageRef
                    result.document.pictures[i].image.uri = image_path
                    logger.debug(f"    Updated existing ImageRef for picture {i+1}: {image_path}")

            images_data.append({
                'image_path': image_path,
                'image_index': i + 1,
                'caption': caption,
                'source_file': basename,
                'width': width,
                'height': height
            })

        except Exception as e:
            logger.warning(f"  ⚠️  Error extracting image {i+1} from {basename}: {e}")
            if os.path.exists(image_path):
                os.remove(image_path)
            continue

    # Collect filtered image paths for URI updates (for consistency with advanced mode)
    filtered_paths = [img['image_path'] for img in images_data]

    # No deduplication in basic mode
    return images_data, filtered_paths, {}


def _extract_images_with_advanced_filtering(
    result,
    file_path: str,
    output_dir: str,
    config
) -> tuple:
    """
    Extract images using advanced two-stage filtering from parser system.

    Stage 1: MD5 hash for byte-level deduplication (~0.002s/image)
    Stage 2: Perceptual hash for visual similarity (~0.012s/image)

    94% faster than naive perceptual hashing approach.

    Args:
        result: Docling ConversionResult
        file_path: Path to source file
        output_dir: Directory to save image files
        config: BatchDoclingConfig instance

    Returns:
        Tuple of (images_data, filtered_paths, dedup_mapping)
    """
    import tempfile
    import shutil

    file_stem = Path(file_path).stem
    basename = os.path.basename(file_path)

    # Step 1: Extract raw images to temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix=f"img_extract_{file_stem}_"))
    raw_images = []

    try:
        for i, figure in enumerate(result.document.pictures):
            temp_image_path = temp_dir / f"{file_stem}_image_{i+1}.png"

            # Extract image using existing helper
            if _extract_image_from_figure(figure, str(temp_image_path), result.document):
                raw_images.append({
                    'path': str(temp_image_path),
                    'index': i + 1,
                    'figure': figure  # Store reference to update URI later
                })

        # Step 2: Apply advanced filtering
        image_filter_config = {
            'min_width': config.image_min_width,
            'min_height': config.image_min_height,
            'max_file_size_mb': config.image_max_file_size_mb,
            'min_content_ratio': config.image_min_content_ratio,
            'enable_deduplication': config.enable_image_deduplication,
            'enable_perceptual_dedup': config.enable_perceptual_dedup,
            'perceptual_hash_method': config.perceptual_hash_method,
            'similarity_threshold': config.image_similarity_threshold
        }

        # Create final output directory
        final_output_dir = Path(output_dir)
        final_output_dir.mkdir(parents=True, exist_ok=True)

        # Apply filtering (includes automatic copy to final_output_dir)
        filtered_images, dedup_mapping = filter_images_advanced(
            images=raw_images,
            temp_dir=temp_dir,
            image_filter_config=image_filter_config,
            final_output_dir=final_output_dir
        )

        logger.info(f"  Filtered images: {len(raw_images)} → {len(filtered_images)} " +
                    f"({len(dedup_mapping)} duplicates removed)")

        # Step 3: Update Docling picture URIs to point to filtered images
        # Build mapping from original temp path to final path
        temp_to_final_path = {}
        for img_data in filtered_images:
            if 'original_temp_path' in img_data:
                temp_to_final_path[img_data['original_temp_path']] = img_data['path']

        logger.debug(f"  Built temp-to-final mapping for {len(temp_to_final_path)} filtered images")
        logger.debug(f"  Updating picture URIs in result.document.pictures...")

        # Update picture.image.uri for each picture in the Docling document
        # CRITICAL: We must update result.document.pictures directly, not just the figure references in raw_images
        uri_updates = 0
        for i, picture in enumerate(result.document.pictures):
            # Construct expected temp path for this picture
            temp_image_path = temp_dir / f"{file_stem}_image_{i+1}.png"

            # Check if this image survived filtering
            if str(temp_image_path) in temp_to_final_path:
                final_path = temp_to_final_path[str(temp_image_path)]

                # Update picture.image.uri (NOT picture.uri)
                if hasattr(picture, 'image'):
                    if picture.image is None:
                        # Create new ImageRef if it doesn't exist
                        picture.image = ImageRef(
                            uri=Path(final_path),
                            mimetype="image/png",
                            dpi=72,
                            size=Size(width=0, height=0)
                        )
                        logger.debug(f"    Created new ImageRef for picture {i+1}: {final_path}")
                        uri_updates += 1
                    elif picture.image is not None:
                        # Update existing ImageRef - keep URI as string
                        picture.image.uri = final_path
                        logger.debug(f"    Updated existing ImageRef for picture {i+1}: {final_path}")
                        uri_updates += 1
                else:
                    logger.warning(f"    Picture {i+1} has no 'image' attribute - cannot update URI")
            else:
                logger.debug(f"    Picture {i+1} was filtered out - skipping URI update")

        logger.info(f"  Updated {uri_updates} picture URIs in Docling document")

        # Step 4: Generate captions for filtered images
        images_data = []
        for img_data in filtered_images:
            image_path = img_data['path']
            image_index = img_data['index']

            # Get image dimensions
            with Image.open(image_path) as img:
                width, height = img.size

            # Generate caption (LLM or fallback)
            caption = _generate_image_caption(image_path, config)

            images_data.append({
                'image_path': image_path,
                'image_index': image_index,
                'caption': caption,
                'source_file': basename,
                'width': width,
                'height': height
            })

        # Collect filtered image paths for URI updates
        filtered_paths = [img_data['path'] for img_data in filtered_images]

        return images_data, filtered_paths, dedup_mapping

    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def extract_images_from_docling(result, file_path: str, output_dir: str = "./extracted_images",
                                min_width: int = 50, min_height: int = 50, config=None) -> tuple:
    """
    Extract images from Docling result with advanced filtering and deduplication.

    Uses two-stage hybrid hashing strategy from parser system for 94% faster performance
    when advanced filtering is available and enabled.

    Args:
        result: Docling ConversionResult
        file_path: Path to source file
        output_dir: Directory to save image files
        min_width: Minimum image width for filtering
        min_height: Minimum image height for filtering
        config: BatchDoclingConfig instance (optional, for advanced filtering)

    Returns:
        Tuple of (images_data, filtered_paths, dedup_mapping)
    """
    images_data = []
    filtered_paths = []
    dedup_mapping = {}

    if not hasattr(result.document, 'pictures') or not result.document.pictures:
        return images_data, filtered_paths, dedup_mapping

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    file_stem = Path(file_path).stem
    basename = os.path.basename(file_path)

    # Check if advanced filtering is available and enabled
    use_advanced_filtering = (
        ADVANCED_FILTERING_AVAILABLE and
        config and
        getattr(config, 'enable_image_deduplication', False)
    )

    if use_advanced_filtering:
        # Use advanced two-stage filtering from parser system
        images_data, filtered_paths, dedup_mapping = _extract_images_with_advanced_filtering(
            result, file_path, output_dir, config
        )
    else:
        # Fall back to basic filtering (existing implementation)
        images_data, filtered_paths, dedup_mapping = _extract_images_with_basic_filtering(
            result, file_path, output_dir, min_width, min_height, config
        )

    return images_data, filtered_paths, dedup_mapping


def convert_pdf_to_documents_docling(pdf_path: str, folder_tags: List[str],
                                     config=None, session_timestamp: Optional[str] = None) -> List[Document]:
    """
    Convert PDF to Haystack Documents using Docling with table/image extraction

    Args:
        pdf_path: Path to PDF file
        folder_tags: List of folder tags for metadata
        config: BatchDoclingConfig instance
        session_timestamp: Timestamp for this processing session (YYYYMMDD_HHMMSS)

    Returns:
        List of Haystack Document objects (text, tables, images)
    """
    from haystack.components.preprocessors import DocumentSplitter
    from datetime import datetime

    # Get configuration defaults
    if config is None:
        from generators.batch_docling_config import BatchDoclingConfig
        config = BatchDoclingConfig.default()

    # Update output directories to use session-based paths
    if session_timestamp:
        from pathlib import Path

        # Get source file stem
        file_stem = Path(pdf_path).stem

        # Get base directory (use parsed_data_dir if available)
        base_dir = Path(config.parsed_data_dir) if hasattr(config, 'parsed_data_dir') else Path("./parsed_data")
        session_dir = base_dir / f"{file_stem}_{session_timestamp}"

        # Update output directories to session-based paths
        config.image_output_dir = str(session_dir / "image_files")
        config.table_output_dir = str(session_dir / "tables")
    elif not session_timestamp:
        # Generate one if not provided
        session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_documents = []
    basename = os.path.basename(pdf_path)

    try:
        # Get shared converter
        converter = get_or_create_converter(config)

        # Convert PDF
        result = converter.convert(pdf_path)

        # 1. Extract tables → Parquet files
        tables = extract_tables_from_docling(result, pdf_path, config.table_output_dir)
        for table in tables:
            table_doc = Document(
                content=table['markdown'],
                meta={
                    'source_file': basename,
                    'folder_tags': folder_tags,
                    'document_tag': "/".join(folder_tags) if folder_tags else "root",
                    'file_type': "pdf",
                    'content_type': "table",
                    'table_index': table['table_index'],
                    'parquet_path': table['parquet_path'],
                    'row_count': table['row_count'],
                    'column_count': table['column_count']
                }
            )
            all_documents.append(table_doc)

        # 2. Extract images → PNG files (with advanced filtering and deduplication)
        # Note: This also updates Docling figure URIs to point to filtered images
        images_data, filtered_paths, dedup_mapping = extract_images_from_docling(
            result, pdf_path, config.image_output_dir,
            config.image_min_width, config.image_min_height, config
        )

        for image in images_data:
            image_doc = Document(
                content=image['caption'],
                meta={
                    'source_file': basename,
                    'folder_tags': folder_tags,
                    'document_tag': "/".join(folder_tags) if folder_tags else "root",
                    'file_type': "pdf",
                    'content_type': "image",
                    'image_index': image['image_index'],
                    'image_path': image['image_path'],
                    'width': image['width'],
                    'height': image['height']
                }
            )
            all_documents.append(image_doc)

        # 3. Extract text → chunked documents (with REFERENCED image mode)
        # Images are now properly referenced in markdown since figure URIs were updated above
        text_content = extract_text_from_docling(result, pdf_path, image_mode=ImageRefMode.REFERENCED)

        # Collect image and table URIs for text document metadata
        image_uris = [img['image_path'] for img in images_data]
        table_uris = [table['parquet_path'] for table in tables]

        text_doc = Document(
            content=text_content,
            meta={
                'source_file': basename,
                'folder_tags': folder_tags,
                'document_tag': "/".join(folder_tags) if folder_tags else "root",
                'file_type': "pdf",
                'content_type': "text",
                'has_tables': len(tables) > 0,
                'table_count': len(tables),
                'image_count': len(images_data),
                'image_uris': image_uris,  # Add image URIs
                'table_uris': table_uris   # Add table URIs
            }
        )

        # Chunk text documents
        splitter = DocumentSplitter(
            split_by=config.split_by,
            split_length=config.chunk_size,
            split_overlap=config.chunk_overlap
        )
        chunked_result = splitter.run(documents=[text_doc])
        chunked_documents = chunked_result["documents"]

        all_documents.extend(chunked_documents)

    except Exception as e:
        logger.error(f"  ✗ Error processing PDF {basename}: {e}")
        raise

    return all_documents


def convert_text_to_documents_docling(text_path: str, folder_tags: List[str],
                                      config=None, session_timestamp: Optional[str] = None) -> List[Document]:
    """
    Convert text/markdown file to Haystack Documents using Docling

    Args:
        text_path: Path to text/markdown file
        folder_tags: List of folder tags for metadata
        config: BatchDoclingConfig instance
        session_timestamp: Timestamp for this processing session (YYYYMMDD_HHMMSS)

    Returns:
        List of Haystack Document objects
    """
    from haystack.components.preprocessors import DocumentSplitter
    from datetime import datetime

    # Get configuration defaults
    if config is None:
        from generators.batch_docling_config import BatchDoclingConfig
        config = BatchDoclingConfig.default()

    # Update output directories to use session-based paths
    if session_timestamp:
        from pathlib import Path

        # Get source file stem
        file_stem = Path(text_path).stem

        # Get base directory (use parsed_data_dir if available)
        base_dir = Path(config.parsed_data_dir) if hasattr(config, 'parsed_data_dir') else Path("./parsed_data")
        session_dir = base_dir / f"{file_stem}_{session_timestamp}"

        # Update output directories to session-based paths
        config.image_output_dir = str(session_dir / "image_files")
        config.table_output_dir = str(session_dir / "tables")
    elif not session_timestamp:
        # Generate one if not provided
        session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    basename = os.path.basename(text_path)
    file_extension = Path(text_path).suffix.lower()

    try:
        # Get shared converter
        converter = get_or_create_converter(config)

        # Handle .txt files by converting to .md format (Docling doesn't support plain text)
        if file_extension == ".txt":
            logger.info(f"Converting .txt file to markdown format: {basename}")

            # Try reading with multiple encodings (UTF-8 → Latin-1 → CP1252 → ASCII)
            txt_content = None
            encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii']

            for encoding in encodings:
                try:
                    with open(text_path, 'r', encoding=encoding) as f:
                        txt_content = f.read()
                    logger.debug(f"Successfully read {basename} with encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue

            if txt_content is None:
                raise ValueError(f"Could not read {basename} with any supported encoding: {encodings}")

            # Create temporary markdown file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as md_file:
                md_file.write(txt_content)
                md_temp_path = md_file.name

            logger.debug(f"Created temporary .md file: {md_temp_path}")

            try:
                # Convert the temporary markdown file
                result = converter.convert(md_temp_path)
            finally:
                # Clean up temporary file
                os.remove(md_temp_path)
                logger.debug(f"Cleaned up temporary markdown file: {md_temp_path}")
        else:
            # Convert markdown or other supported formats directly
            result = converter.convert(text_path)

        # Extract text content
        text_content = extract_text_from_docling(result, text_path)

        # Create document
        text_doc = Document(
            content=text_content,
            meta={
                'source_file': basename,
                'folder_tags': folder_tags,
                'document_tag': "/".join(folder_tags) if folder_tags else "root",
                'file_type': "text",
                'file_extension': file_extension,
                'content_type': "text"
            }
        )

        # Chunk documents
        splitter = DocumentSplitter(
            split_by=config.split_by,
            split_length=config.chunk_size,
            split_overlap=config.chunk_overlap
        )
        chunked_result = splitter.run(documents=[text_doc])
        chunked_documents = chunked_result["documents"]

        return chunked_documents

    except Exception as e:
        logger.error(f"  ✗ Error processing text file {basename}: {e}")
        raise


def convert_image_to_documents_docling(
    image_path: str,
    folder_tags: List[str],
    config=None,
    session_timestamp: Optional[str] = None
) -> List[Document]:
    """
    Convert standalone image file to Haystack Documents using simplified approach.

    Similar to parsers/docling_parsers/image_parser.py but without OCR (for speed).
    Focuses on LLM-based captioning and metadata generation.

    Args:
        image_path: Path to image file (PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP)
        folder_tags: List of folder tags for metadata
        config: BatchDoclingConfig instance
        session_timestamp: Timestamp for this processing session (YYYYMMDD_HHMMSS)

    Returns:
        List of Haystack Document objects (single document)
    """
    import shutil
    from datetime import datetime

    # Get configuration defaults
    if config is None:
        from generators.batch_docling_config import BatchDoclingConfig
        config = BatchDoclingConfig.default()

    # Generate session timestamp if not provided
    if not session_timestamp:
        session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get source file stem
    file_stem = Path(image_path).stem
    basename = os.path.basename(image_path)

    # Update output directories to use session-based paths
    base_dir = Path(config.parsed_data_dir) if hasattr(config, 'parsed_data_dir') else Path("./parsed_data")
    session_dir = base_dir / f"{file_stem}_{session_timestamp}"
    output_image_dir = session_dir / "image_files"
    output_image_dir.mkdir(parents=True, exist_ok=True)

    # Copy image to structured directory
    output_image_path = output_image_dir / basename
    shutil.copy2(image_path, output_image_path)

    # Get image dimensions
    with Image.open(output_image_path) as img:
        width, height = img.size

    # Generate caption
    caption = _generate_image_caption(str(output_image_path), config)

    # Create Haystack document
    image_doc = Document(
        content=caption,
        meta={
            'source_file': basename,
            'folder_tags': folder_tags,
            'document_tag': "/".join(folder_tags) if folder_tags else "root",
            'file_type': Path(image_path).suffix.lower().lstrip('.'),
            'content_type': 'image',
            'image_index': 1,
            'image_path': str(output_image_path),
            'width': width,
            'height': height
        }
    )

    return [image_doc]
