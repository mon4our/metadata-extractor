from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import PyPDF2
from tika import parser
from pathlib import Path
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import json
import mimetypes
import platform
from collections import Counter
import requests
import time

@dataclass
class ValidationReport:
    """Stores validation results for extracted metadata"""
    is_valid: bool
    missing_fields: List[str]
    validation_errors: List[str]

class MetadataExtractor:
    """Enhanced metadata extractor with Windows compatibility"""
    
    REQUIRED_FIELDS = {
        'file_type', 'file_size', 'timestamps', 
        'schema', 'volumetrics', 'content_summary'
    }
    
    def __init__(self, max_workers: int = 4, content_summary_length: int = 1000):
        self.max_workers = max_workers
        self.content_summary_length = content_summary_length
        self.logger = self._setup_logging()
        mimetypes.init()
        
    @staticmethod
    def _setup_logging():
        logger = logging.getLogger('MetadataExtractor')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Make a call to Ollama API."""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b-instruct-q8_0",
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json()['response']
        except Exception as e:
            print(f"Error calling Ollama: {str(e)}")
            return None
        
    def _call_jsonaut(self, json: str):
        """Make call to JSONaut API"""
        api = "https://api.jsonaut.com/json/v1/repair"
        try:
            response = requests.post(
                api,
                json={
                    "json_content": json,
                    "token": "YOUR_API_KEY"
                }
            )
            return response
        except Exception as e:
            print("Issue with jsonaut request")
            return e
    def _clean_json_through_jsonaut(self, json: str):
        """
        Clean and normalize JSON string for reliable parsing through the JSONaut api.
        Args:
            json_str: Raw JSON string that might contain inconsistencies
            
        Returns:
            Cleaned JSON object ready for parsing
        """
        response = self._call_jsonaut(json)
        if(response.json()['data']['json_status'] == "VALID" and response.json()['data']['json_repaired'] == "YES"):
            return response.json()['data']['json_data']
        else:
            raise Exception
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type using mimetypes library"""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            if file_path.suffix.lower() == '.pdf':
                mime_type = 'application/pdf'
            elif file_path.suffix.lower() == '.csv':
                mime_type = 'text/csv'
            elif file_path.suffix.lower() in ['.xls', '.xlsx']:
                mime_type = 'application/vnd.ms-excel'
            else:
                mime_type = 'application/octet-stream'
        return mime_type
    
    def _extract_tika_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract Tika metadata"""
        print("Extracting other file type metadata....")
        stats = file_path.stat()
        parsed = parser.from_file(str(file_path))
        metadata = parsed.get("metadata", {})
        content = parsed.get("content", "")
        shortened_content = content[:500]
        
        volumetrics = {
            'character_count': metadata.get('meta:character-count-with-spaces', ''),
            'word_count': metadata.get('meta:word-count', ''),
            'line_count': metadata.get('meta:line-count', ''),
            'page_count': metadata.get('meta:page-count', ''),
        }
        
        return {
            'filename': file_path.name,
            'file_type': file_path.suffix.lower(),
            'file_size': stats.st_size,
            'format': metadata.get('dc:format', ''),
            'timestamps': {
                'created': metadata.get('dcterms:created', ''),
                'modified': metadata.get('dcterms:modified', ''),
                'accessed': datetime.fromtimestamp(stats.st_atime).isoformat(),
                'metadata_extracted': datetime.now().isoformat(),
            },
            'content_type': metadata.get('Content-Type', ''),
            'schema': 'tika',
            'content_encoding': metadata.get('Content-Encoding', ''),
            'volumetrics': volumetrics,
            'content_summary': self._generate_content_summary(shortened_content)
        }
    
    def _extract_pdf_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract PDF metadata"""
        print("Extracting pdf metadata....")
        with open(file_path, 'rb') as f:
            try:
                stats = file_path.stat()
                
                parsed = parser.from_file(str(file_path))
                metadata = parsed.get("metadata", {})
                
                pdf = PyPDF2.PdfReader(f)
                
                # Extract text for content summary
                text_content = []
                for page in pdf.pages:
                    try:
                        text_content.append(page.extract_text())
                    except Exception as e:
                        self.logger.warning(f"Error extracting text from page: {str(e)}")
                
                text_content = ' '.join(text_content)
                text = ' '.join(text_content.split())
                sentences = text.split('.')
                words = text.split()
                sentences = [s for s in text.split('.') if s.strip()]
                word_freq = Counter(words)
                common_words = [word for word, count in word_freq.most_common(5)]

                schema = []
                responses = self.extract_tables_from_pdf(text)
                for response in responses:
                    if "Table not found" not in response:
                        try:
                            cleaned_response = self._clean_json_through_jsonaut(response.replace('"',r'\"'))
                            schema.append(cleaned_response)
                        except Exception as e:
                            print(e)
                            print(response)

                volumetrics = {
                    'page_count': len(pdf.pages),
                    'characters_per_page': metadata.get('pdf:charsPerPage', ''),
                    'character_count': len(text),
                    'word_count': len(words),
                    'sentence_count': len(sentences),
                    'average_word_length': round(sum(len(word) for word in words) / len(words), 2) if words else 0,
                    'common_words': common_words
                }

                summary_content = []
                for page in pdf.pages[:5]:  # First 5 pages for summary
                    try:
                        summary_content.append(page.extract_text())
                    except Exception as e:
                        self.logger.warning(f"Error extracting text from page: {str(e)}")
                
                return {
                    'filename': file_path.name,
                    'file_type': file_path.suffix.lower(),
                    'file_size': stats.st_size,
                    'format': metadata.get('dc:format', ''),
                    'timestamps': {
                        'created': metadata.get('dcterms:created', ''),
                        'modified': metadata.get('dcterms:modified', ''),
                        'accessed': datetime.fromtimestamp(stats.st_atime).isoformat(),
                        'metadata_extracted': datetime.now().isoformat(),
                    },
                    'author': metadata.get('pdf:producer', ''),
                    'schema': schema,
                    'volumetrics': volumetrics,
                    'content_summary': self._generate_content_summary(summary_content)
                }
            except Exception as e:
                self.logger.error(f"Error processing PDF: {str(e)}")
                return {
                    'schema': 'pdf',
                    'volumetrics': {'file_size_mb': round(file_path.stat().st_size / (1024 * 1024), 2)},
                    'content_summary': {'preview': '', 'statistics': {}}
                }
    
    def extract_tables_from_pdf(self, text_content: str) -> None:
        """Sends a request to ollama to extract tables (if they exist) from the given pdf text."""
        responses = []
        batch_size = 4000
        batches = [text_content[i:i+batch_size] 
            for i in range(0, len(text_content), batch_size)]
        for batch in batches:

            prompt = f"""Extract all tables from the following text. For each table found: Identify column headers/names and the data type they contain. Also a 10 word description of the table's contents.
            Return the data in a structured format like:
            {{
                "table 1": [
                    {{"description": "table 1 description"}},
                    {{"column": "column 1", "type": "column 1 type"}},
                    {{"column": "column 2", "type": "column 2 type"}},...
                ],
                "table 2": [
                    {{"description": "table 2 description"}},
                    {{"column": "column 1", "type": "column 1 type"}},
                    {{"column": "column 2", "type": "column 2 type"}},...
                ],...
            }}
            If no tables are found, return {{"Table not found": []}}. DO NOT add any extra text/symbol before and after the json object.
            
            Text content:
            {batch}
            """            
            # Call LLM with delay
            time.sleep(5)
            try:
                responses.append(self._call_ollama(prompt))
            except Exception as e:
                print(e)
        return responses
    
    def _extract_tabular_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract tabular metadata"""
        print("Extracting spreadsheet metadata....")
        try:
            stats = file_path.stat()
                
            parsed = parser.from_file(str(file_path))
            metadata = parsed.get("metadata", {})
            df = pd.read_csv(file_path) if file_path.suffix.lower() == '.csv' else pd.read_excel(file_path)
            print(df)

            schema_prompt = f"""
            Analyze this Excel data: {df.head(10)}
            Ignore all Columns that are unnamed. In json format, give me the:
            - Column headers/names
            - Sub-columns (if they exist)
            - Sub-columns of sub-columns (if they exist)
            - Data Types
            - A short description of the table's contents
            In exactly this format:
            {{
                "table": [
                    {{"description": "table 1 description"}},
                    {{"column": "column 1", "sub-columns": ["sub-column 1", "sub-column 2",...], "type": "column 1 type"}},
                    {{"column": "column 2", "sub-columns": ["sub-column 1", "sub-column 2",...], "type": "column 2 type"}},....
                ]
            }}
            Provide ONLY the json object.
            """

            response = self._call_ollama(schema_prompt)
            try:
                response = self._clean_json_through_jsonaut(response.replace('"',r'\"'))
                print(response)
            except Exception as e:
                print(e)

            cleaned_data = []
    
            for item in response["table"]:
                # Create a copy of the item to avoid modifying the original
                cleaned_item = item.copy()
                
                # Check if sub-columns exists and is empty
                if "sub-columns" in cleaned_item and not cleaned_item["sub-columns"]:
                    del cleaned_item["sub-columns"]
                    
                cleaned_data.append(cleaned_item)
            response["table"] = cleaned_data
            print(response)
            
            volumetrics = {
                'content_length': metadata.get('Content-Length', ''),
                'row_count': int(len(df)),
                'column_count': int(len(df.columns)),
                'null_count': int(df.isnull().sum().sum()),
                'duplicate_rows': int(df.duplicated().sum())
            }
            
            return {
                'filename': file_path.name,
                'file_type': file_path.suffix.lower(),
                'file_size': stats.st_size,
                'format': metadata.get('dc:format', ''),
                'timestamps': {
                    'created': metadata.get('dcterms:created', ''),
                    'modified': metadata.get('dcterms:modified', ''),
                    'accessed': datetime.fromtimestamp(stats.st_atime).isoformat(),
                    'metadata_extracted': datetime.now().isoformat(),
                },
                'author': metadata.get('dc:creator', ''),
                'last_modified_by': metadata.get('meta:last-author', ''),
                'schema': response,
                'volumetrics': volumetrics,
                'content_summary': self._generate_content_summary(df)
            }
        except Exception as e:
            self.logger.error(f"Error processing tabular data: {str(e)}")
            return {
                'schema': 'tabular',
                'volumetrics': {'file_size_mb': round(file_path.stat().st_size / (1024 * 1024), 2)},
                'content_summary': ''
            }
    
    def _generate_content_summary(self, text: str) -> str:
        """Generate content summary"""
        prompt = f"Generate a short 100 word summary of the information contained in the file based on {text}. Return ONLY the summary, no introductory sentences."
        response = self._call_ollama(prompt)
        
        return response
    
    def _extract_enhanced_metadata(self) -> Dict[str, Any]:
        """Extract additional enhanced metadata"""
        return {
            'system_info': {
                'processing_node': platform.node(),
                'os': platform.system(),
                'python_version': platform.python_version()
            },
        }
    
    def _validate_metadata(self, metadata: Dict[str, Any]) -> ValidationReport:
        """Validate enhanced metadata"""
        missing_fields = self.REQUIRED_FIELDS - set(metadata.keys())
        validation_errors = []
        
        if missing_fields:
            validation_errors.append(f"Missing required fields: {missing_fields}")
            
        # Validate volumetrics
        if 'volumetrics' in metadata:
            if not isinstance(metadata['volumetrics'], dict):
                validation_errors.append("Volumetrics must be a dictionary")
            elif not metadata['volumetrics']:
                validation_errors.append("Volumetrics cannot be empty")
                
        # Validate timestamps
        if 'timestamps' in metadata:
            if not isinstance(metadata['timestamps'], dict):
                validation_errors.append("Timestamps must be a dictionary")
            required_timestamps = {'created', 'modified', 'accessed'}
            missing_timestamps = required_timestamps - set(metadata['timestamps'].keys())
            if missing_timestamps:
                validation_errors.append(f"Missing required timestamps: {missing_timestamps}")
                
        return ValidationReport(
            is_valid=len(validation_errors) == 0,
            missing_fields=list(missing_fields),
            validation_errors=validation_errors
        )
    
    def process_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """Process all files in a directory using thread pool"""
        directory_path = Path(directory_path)
        files = [f for f in directory_path.glob('**/*') if f.is_file()]
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.extract_metadata, files))
            
        return results
    
    def save_results(self, results: List[Dict[str, Any]], output_path: str):
        """Save extraction results to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
            
        self.logger.info(f"Results saved to {output_path}")
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from a given file"""
        try:
            file_path = Path(file_path)            
            mime_type = self._get_mime_type(file_path)
            
            if mime_type == 'application/pdf':
                specific_metadata = self._extract_pdf_metadata(file_path)
            elif mime_type in ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                specific_metadata = self._extract_tabular_metadata(file_path)
            else:
                specific_metadata = self._extract_tika_metadata(file_path)
                
            enhanced_metadata = self._extract_enhanced_metadata()
            metadata = {**specific_metadata, **enhanced_metadata}
            
            validation_report = self._validate_metadata(metadata)
            if not validation_report.is_valid:
                self.logger.warning(f"Validation failed for {file_path}: {validation_report.validation_errors}")
                
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
            raise

if __name__ == "__main__":
    extractor = MetadataExtractor(max_workers=4)
    
    try:
        # Process directory
        results = extractor.process_directory("files")
        extractor.save_results(results, "metadata_results.json")
        
    except Exception as e:
        print(f"Error: {str(e)}")