"""
Docling Configuration for Batch PDF Processing
Simplified configuration without hwtgenielib dependencies
"""

from dataclasses import dataclass, field
from typing import Optional
import yaml
from pathlib import Path


@dataclass
class BatchDoclingConfig:
    """Configuration for Docling document processing"""

    # OCR settings
    do_ocr: bool = False
    ocr_engine: str = "easyocr"  # Options: "easyocr", "tesseract"

    # Table extraction settings
    do_table_structure: bool = True
    table_output_format: str = "parquet"  # Options: "parquet", "csv", "json"

    # Image extraction settings (ENHANCED)
    generate_picture_images: bool = True
    images_scale: float = 1.0
    image_min_width: int = 50
    image_min_height: int = 50

    # Advanced image filtering settings (NEW)
    image_max_file_size_mb: float = 20.0  # Maximum image file size
    image_min_content_ratio: float = 0.1  # Minimum non-white pixel ratio (0.1 = 10%)
    enable_image_deduplication: bool = True  # Enable MD5 + perceptual dedup
    enable_perceptual_dedup: bool = True  # Enable visual similarity detection
    perceptual_hash_method: str = 'dhash'  # Options: 'ahash', 'dhash', 'phash'
    image_similarity_threshold: float = 0.95  # Similarity threshold for duplicates (0.0-1.0)

    # Output directories (dynamically set during processing to session-based paths)
    table_output_dir: str = ""  # Will be set to: {parsed_data_dir}/{file}_{timestamp}/tables
    image_output_dir: str = ""  # Will be set to: {parsed_data_dir}/{file}_{timestamp}/image_files

    # Parsed data artifact storage (base directory for all outputs)
    parsed_data_dir: str = "./parsed_data"  # Base directory for all parsed artifacts
    save_parsed_artifacts: bool = True  # Enable/disable artifact saving

    # Document chunking settings
    chunk_size: int = 800
    chunk_overlap: int = 100
    split_by: str = "word"  # Options: "word", "sentence", "passage"

    # Image captioning settings (Gemini Flash 2.0 vision)
    use_llm_captions: bool = False
    caption_model: str = "gemini-2.0-flash-exp"
    caption_prompt: Optional[str] = None
    caption_timeout: int = 30

    def to_pipeline_options(self):
        """Convert to Docling PdfPipelineOptions format"""
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        return PdfPipelineOptions(
            do_ocr=self.do_ocr,
            do_table_structure=self.do_table_structure,
            generate_picture_images=self.generate_picture_images,
            images_scale=self.images_scale
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'BatchDoclingConfig':
        """Load configuration from YAML file"""
        with open(yaml_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)

    @classmethod
    def default(cls) -> 'BatchDoclingConfig':
        """Create default configuration"""
        return cls()


def load_batch_config(config_path: Optional[str] = None) -> BatchDoclingConfig:
    """
    Load configuration from file or use defaults

    Args:
        config_path: Optional path to YAML config file

    Returns:
        BatchDoclingConfig instance
    """
    if config_path and Path(config_path).exists():
        return BatchDoclingConfig.from_yaml(config_path)
    return BatchDoclingConfig.default()
