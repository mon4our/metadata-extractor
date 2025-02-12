# Metadata Extractor

## Overview
This project utilizes **Ollama** to run a **Generative AI Model** locally for extracting metadata from files.

The selected model is **Llama 3.1 (8b-instruct-q8_0)**, an instruct-based model with **8 billion parameters and quantization 8**, chosen for its balance between accuracy and efficiency.

## Approach
1. **Extract Basic Metadata** using **Apache Tika**.
2. **Determine File Type**:
   - **PDF Files**: Extract detailed metadata using **PyPDF2**.
   - **Spreadsheet Files**: Extract metadata using **Pandas**.
3. **Process PDFs**:
   - Divide content into batches.
   - Send requests to **Ollama API** with a prompt for table extraction in **strict JSON format**.
4. **Process Spreadsheets**:
   - Convert them into a **Pandas DataFrame**.
   - Send the DataFrame to **Ollama API** for table extraction.
5. **Clean Responses**:
   - Utilize **JSONaut API** to clean the JSON output.
6. **Output Metadata**:
   - Consolidate metadata into a structured **JSON object**.
   - Store results in a file: `metadata_results.json`.
7. **Output PDF Report**:
   - Read `metadata_results.json` to create a readable PDF report of all the metadata.

## Use of Generative AI
- **Llama 3.1** extracts metadata, including:
  - Table name
  - Column headers
  - Data types
  - Table descriptions
- **JSONaut API** cleans the JSON output.

## Setup Instructions
### 1. Install Ollama
Download and install **Ollama** on your machine. Then, open a terminal and run:
```sh
ollama run llama3.1:8b-instruct-q8_0
```
This will download the **Llama 3.1 model** and set up an API to send requests.

### 2. Install Dependencies
Save the project code in a folder and install required Python libraries:
```sh
pip install
```

### 3. Set Up JSONaut API
1. **Create a free account** on **JSONaut**.
2. Get your **API key** (allows up to 8000 characters per request).
3. Replace `YOUR_API_KEY` on **line 73** of the code with your actual API key.

### 4. Prepare Your Files
1. **Create a folder** named `files` in the project directory.
2. **Place all files** to be processed inside `files`.

### 5. Run the Metadata Extractor
Execute the script to generate metadata:
```sh
python metadata_extractor.py
```
This will create a JSON file: `metadata_results.json`.

### 6. Generate PDF Reports
To create PDF reports of the extracted metadata:
```sh
python pdf_generator.py
```
This will generate **PDF reports** for each file inside the `files` folder.

## Output
- **metadata_results.json** (contains extracted metadata in JSON format).
- **PDF reports** summarizing metadata.

---
### Notes
- Ensure Ollama and JSONaut API are correctly set up before running the scripts.
- The project requires an **internet connection** to download the AI model initially and to send requests to JSONaut.

---
