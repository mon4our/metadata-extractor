from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from datetime import datetime
from typing import Dict, Any
from textwrap import wrap

def format_timestamp(timestamp_str: str) -> str:
    """Convert ISO timestamp to a more readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y %I:%M %p")
    except ValueError:
        return timestamp_str

def format_file_size(size_in_bytes: int) -> str:
    """Convert file size to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} TB"

def create_metadata_pdf(metadata: Dict[str, Any], output_filename: str = "metadata_report.pdf"):
    """Generate a PDF report from metadata dictionary."""
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    content_style = ParagraphStyle(
        'ContentStyle',
        parent=normal_style,
        spaceBefore=6,
        spaceAfter=6,
        leftIndent=20
    )
    
    story = []
    
    # Title
    story.append(Paragraph(f"Metadata Report: {metadata['filename']}", title_style))
    story.append(Spacer(1, 0.25*inch))
    
    # File Information Section
    story.append(Paragraph("File Information", heading_style))
    file_info = [
        ["File Type:", metadata['file_type']],
        ["File Size:", format_file_size(metadata['file_size'])]
    ]
    if 'format' in metadata:
        file_info.append(["Format:", metadata['format']])
        
    t = Table(file_info, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.25*inch))
    
    # Timestamps Section
    story.append(Paragraph("Timestamps", heading_style))
    timestamps_data = [[k.replace('_', ' ').title() + ":", format_timestamp(v)] 
                      for k, v in metadata['timestamps'].items()]
    t = Table(timestamps_data, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.25*inch))
    
    # Authorship Section
    if 'author' in metadata:
        story.append(Paragraph("Authorship", heading_style))
        author_info = [["Created By:", metadata['author']]]
        if 'last_modified_by' in metadata:
            author_info.append(["Last Modified By:", metadata['last_modified_by']])
        
        t = Table(author_info, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25*inch))
    
    # Schema Information Section
    story.append(Paragraph("Schema Information", heading_style))
    # For spreadsheet
    if metadata['file_type'] == '.xlsx':
        for table in metadata['schema']['table']:
            if 'description' in table:
                story.append(Paragraph(f"Table Description:", content_style))
                story.append(Paragraph(table['description'], content_style))
            elif 'column' in table:
                column_info = [
                    ["Column:", table['column']],
                    ["Type:", table['type']]
                ]
                if 'sub-columns' in table:
                    sub_cols = ", ".join(table['sub-columns'])
                    column_info.append(["Sub-columns:", sub_cols])
                
                t = Table(column_info, colWidths=[2*inch, 4*inch])
                t.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.15*inch))
        
        story.append(Paragraph("Volumetrics", heading_style))
        volumetrics_data = [
            ["Content Length:", f"{metadata['volumetrics']['content_length']} bytes"],
            ["Row Count:", str(metadata['volumetrics']['row_count'])],
            ["Column Count:", str(metadata['volumetrics']['column_count'])],
            ["Null Values:", str(metadata['volumetrics']['null_count'])],
            ["Duplicate Rows:", str(metadata['volumetrics']['duplicate_rows'])]
        ]
        t = Table(volumetrics_data, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25*inch))

    # For pdf
    elif metadata['file_type'] == '.pdf':
        for table_dict in metadata['schema']:
            for table_name, data in table_dict.items():
                story.append(Paragraph(f"Table: {table_name}", content_style))
                for columns in data:
                    if "description" in columns:
                        story.append(Paragraph(columns['description'], content_style))
                    else:
                        try:
                            wrapped_col = '\n'.join(wrap(columns['column'], width=60)) if len(columns['column'])>60 else columns['column']
                        except Exception as e:
                            wrapped_col = columns['column']
                        column_info = [
                            ["Column:", wrapped_col],
                            ["Type:", columns['type']]
                        ]
                        t = Table(column_info, colWidths=[2*inch, 4*inch])
                        t.setStyle(TableStyle([
                            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                            ('PADDING', (0, 0), (-1, -1), 6),
                        ]))
                        story.append(t)
        story.append(Paragraph("Schema Information", heading_style))
        story.append(Spacer(1, 0.25*inch))

        
        story.append(Paragraph("Volumetrics", heading_style))
        chars_per_page = metadata['volumetrics']['characters_per_page']
        wrapped_chars = '\n'.join(wrap(', '.join(chars_per_page), width=60))
        volumetrics_data = [
            ["Page Count:", f"{metadata['volumetrics']['page_count']} pages"],
            ["Characters Per Page:", wrapped_chars],
            ["Character Count:", str(metadata['volumetrics']['character_count'])],
            ["Word Count:", str(metadata['volumetrics']['word_count'])],
            ["Sentence Count:", str(metadata['volumetrics']['sentence_count'])],
            ["Average Word Length:", str(metadata['volumetrics']['average_word_length'])],
            ['Common Words:', ', '.join(metadata['volumetrics']['common_words'][:5])]
        ]
        t = Table(volumetrics_data, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25*inch))
    
    # For other files
    else:
        story.append(Paragraph("Volumetrics", heading_style))
        volumetrics_data = [
            ["Character Count:", f"{metadata['volumetrics']['character_count']}"],
            ["Word Count:", str(metadata['volumetrics']['word_count'])],
            ["Line Count:", str(metadata['volumetrics']['line_count'])],
            ["Page Count:", str(metadata['volumetrics']['page_count'])],
        ]
        t = Table(volumetrics_data, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25*inch))
    # Content Summary Section (PDF-specific)
    if 'content_summary' in metadata:
        story.append(Paragraph("Content Summary", heading_style))
        story.append(Paragraph(metadata['content_summary'], content_style))
        story.append(Spacer(1, 0.25*inch))
    
    # System Information Section
    story.append(Paragraph("System Information", heading_style))
    system_info = [
        ["Processing Node:", metadata['system_info']['processing_node']],
        ["Operating System:", metadata['system_info']['os']],
        ["Python Version:", metadata['system_info']['python_version']]
    ]
    t = Table(system_info, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    
    # Build the PDF
    doc.build(story)

# Example usage
if __name__ == "__main__":
    import json
    
    with open('metadata_results.json', 'r') as f:
        metadata = json.load(f)
        for no, file in enumerate(metadata):
            create_metadata_pdf(file, f"report_{no+1}.pdf")