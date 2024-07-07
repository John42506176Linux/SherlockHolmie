from langchain.schema import BaseOutputParser
from langchain_core.output_parsers.transform import BaseCumulativeTransformOutputParser
from typing import  Optional, Dict, Any

class ErrorJsonParser(BaseOutputParser[Dict[str, Any]]):
    """Error JSON parser with error handling."""

    json_parser:Optional[BaseCumulativeTransformOutputParser]  = None

    def parse(self, text: str) -> Dict[str, Any]:
        try:
            return self.json_parser.parse(text)
        except Exception as e:
            print(f"JSON parsing failed: {e}")
            return {}  # Return an empty dict on parsing failure
    
    def get_format_instructions(self) -> str:
        """Get the format instructions for the underlying JsonOutputParser."""
        return self.json_parser.get_format_instructions()
    
    @property
    def _type(self) -> str:
        return "error_json_output_parser"