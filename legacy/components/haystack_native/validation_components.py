"""
Pydantic validation components for type-safe pipeline data handling.
Replaces ad-hoc validation with structured, fail-fast validation patterns.
"""

from haystack import component
from haystack.components.validators import JsonSchemaValidator
from pydantic import ValidationError, BaseModel
from models.pydantic_dtos import ParallelResults, ValidatedScenario, IntentAnalysis, RAGContext, SkillCheckResult
from typing import Dict, Any, Type, Union, List

class PydanticValidator:
    """Base validator class - not a component itself"""
    
    def __init__(self, model_class: Type[BaseModel]):
        self.model_class = model_class
        self.model_name = model_class.__name__
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Union[Dict[str, Any], str]]:
        """Validate input data against Pydantic model"""
        try:
            validated = self.model_class.model_validate(data)
            return {"validated_data": validated.model_dump()}
        except ValidationError as e:
            error_msg = f"Validation failed for {self.model_name}: {str(e)}"
            return {"validation_error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected validation error for {self.model_name}: {str(e)}"
            return {"validation_error": error_msg}

@component
class ScenarioValidator:
    """Specialized validator for scenario output validation"""
    
    def __init__(self):
        self.validator = PydanticValidator(ValidatedScenario)
    
    @component.output_types(validated_scenario=Dict[str, Any], validation_error=str)
    def run(self, scenario_data: Dict[str, Any]) -> Dict[str, Union[Dict[str, Any], str]]:
        """Validate scenario data with game-specific checks"""
        
        # First run standard Pydantic validation
        result = self.validator.validate(scenario_data)
        
        if "validation_error" in result:
            return result
            
        # Additional game-specific validation
        validated_data = result["validated_data"]
        
        # Ensure scene is not empty
        if not validated_data.get("scene", "").strip():
            return {"validation_error": "Scene cannot be empty"}
        
        # Ensure at least one choice is provided
        choices = validated_data.get("choices", [])
        if not choices:
            return {"validation_error": "At least one choice must be provided"}
        
        # Validate choice structure
        for i, choice in enumerate(choices):
            if not isinstance(choice, dict):
                return {"validation_error": f"Choice {i} must be a dictionary"}
            if "text" not in choice:
                return {"validation_error": f"Choice {i} must have 'text' field"}
        
        return {"validated_scenario": validated_data}

@component
class ParallelResultsValidator:
    """Specialized validator for parallel processing results"""
    
    def __init__(self):
        self.validator = PydanticValidator(ParallelResults)
    
    @component.output_types(validated_data=Dict[str, Any], validation_error=str)
    def run(self, data: Dict[str, Any]) -> Dict[str, Union[Dict[str, Any], str]]:
        """Validate parallel results data"""
        return self.validator.validate(data)

@component
class IntentValidator:
    """Specialized validator for intent analysis results"""
    
    def __init__(self):
        self.validator = PydanticValidator(IntentAnalysis)
    
    @component.output_types(validated_data=Dict[str, Any], validation_error=str)
    def run(self, data: Dict[str, Any]) -> Dict[str, Union[Dict[str, Any], str]]:
        """Validate intent analysis data"""
        return self.validator.validate(data)

class RequestValidator(BaseModel):
    """Pydantic model for request validation"""
    player_input: str
    intent: str
    confidence: float
    flags: Dict[str, bool]

class ResponseValidator(BaseModel):
    """Pydantic model for response validation"""
    scene: str
    choices: List[Dict[str, Any]]
    success: bool

@component
class CompositeValidator:
    """Validate multiple data types in a single component"""
    
    def __init__(self):
        self.validators = {
            "scenario": ScenarioValidator(),
            "parallel_results": ParallelResultsValidator(),
            "intent": IntentValidator()
        }
    
    @component.output_types(
        validated_data=Dict[str, Any], 
        validation_error=str,
        validation_type=str
    )
    def run(self, data: Dict[str, Any], validation_type: str = "scenario") -> Dict[str, Any]:
        """Validate data using the specified validator type"""
        
        if validation_type not in self.validators:
            return {
                "validation_error": f"Unknown validation type: {validation_type}",
                "validation_type": validation_type
            }
        
        validator = self.validators[validation_type]
        result = validator.run(data)
        result["validation_type"] = validation_type
        
        return result

@component
class DataSanitizer:
    """Sanitize and clean data before validation"""
    
    @component.output_types(sanitized_data=Dict[str, Any])
    def run(self, raw_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Clean and sanitize input data"""
        
        sanitized = {}
        
        for key, value in raw_data.items():
            if isinstance(value, str):
                # Clean string values
                sanitized[key] = value.strip()
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                # Sanitize list items
                sanitized[key] = self._sanitize_list(value)
            else:
                sanitized[key] = value
        
        return {"sanitized_data": sanitized}
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary values"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = value.strip()
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = self._sanitize_list(value)
            else:
                sanitized[key] = value
        return sanitized
    
    def _sanitize_list(self, data: List[Any]) -> List[Any]:
        """Sanitize list items"""
        sanitized = []
        for item in data:
            if isinstance(item, str):
                sanitized.append(item.strip())
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item))
            elif isinstance(item, list):
                sanitized.append(self._sanitize_list(item))
            else:
                sanitized.append(item)
        return sanitized