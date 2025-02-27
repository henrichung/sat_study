#!/usr/bin/env python3
"""
Core functions for generating SAT worksheets.
This module contains functions for:
  • Loading and filtering questions
  • Shuffling options and converting LaTeX to images
  • Processing question content (including inline images)
  • Creating worksheets using ReportLab
  • Validating arguments and distributing questions across pages
"""
import json
import os
import random
import math
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import tempfile
import uuid
from PIL import Image as PILImage
from xml.sax.saxutils import escape
import base64
import re

# Import LaTeX utilities
from src.core.latex import latex_to_image

def load_questions(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def filter_questions(questions, tags):
    if not tags:
        return questions
    return [q for q in questions if any(tag in q['tags'] for tag in tags)]

def shuffle_options(question):
    if 'options' in question and isinstance(question['options'], dict):
        options_dict = question['options']
        correct_answer = question['answer']
        items = list(options_dict.items())
        random.shuffle(items)
        shuffled_options = dict(items)
        # Reset correct_index based on the new order
        for letter, value in shuffled_options.items():
            if value == correct_answer:
                question['correct_index'] = ord(letter) - ord('A')
                break
        question['options'] = shuffled_options
    return question

def process_question_content(content, style, temp_dir, desired_height_pt=12):
    """Process question content, handling both text with inline LaTeX and images."""
    from reportlab.platypus import KeepTogether

    if isinstance(content, dict):
        text = content.get('text', '')
        image_path = content.get('image', '')
        
        text_flowable = None
        if text:
            parts = text.split('$')
            if len(parts) > 1:  # Contains LaTeX
                markup = ""
                for i, part in enumerate(parts):
                    if i % 2 == 0:
                        markup += escape(part)
                    else:
                        try:
                            img_data = latex_to_image(part)
                            img_data.seek(0)
                            
                            # Get PNG dimensions using PIL
                            pil_img = PILImage.open(img_data)
                            width_px, height_px = pil_img.size
                            width_pt = (width_px / 300) * 72  # Convert from px at 300dpi to points
                            height_pt = (height_px / 300) * 72
                            scale_factor = desired_height_pt / height_pt
                            scaled_width = width_pt * scale_factor
                            
                            # Convert to base64 and embed as PNG
                            img_data.seek(0)
                            b64_data = base64.b64encode(img_data.read()).decode('utf-8')
                            markup += (f'<img src="data:image/png;base64,{b64_data}" '
                                     f'width="{scaled_width}pt" height="{desired_height_pt}pt" '
                                     f'valign="middle"/>')
                        except Exception as e:
                            print(f"Warning: LaTeX rendering failed for '{part}': {str(e)}")
                            markup += escape(f'${part}$')
                text_flowable = Paragraph(markup, style)
            else:
                text_flowable = Paragraph(escape(text), style)
                
        if image_path and os.path.exists(image_path):
            image_flowable = Image(image_path, width=6*inch)
            if text_flowable:
                return KeepTogether([text_flowable, Spacer(1, 12), image_flowable])
            return image_flowable
        return text_flowable if text_flowable else Paragraph("", style)
            
    elif isinstance(content, str):
        return Paragraph(escape(content), style)
        
    return Paragraph("", style)

def create_worksheet(questions, output_file, title, include_answers=False):
    from reportlab.lib.pagesizes import letter as page_size
    doc = SimpleDocTemplate(output_file, pagesize=page_size, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    story = []
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    question_style = ParagraphStyle('QuestionStyle', fontSize=12, spaceAfter=6)
    option_style = ParagraphStyle('OptionStyle', fontSize=12, leftIndent=20, spaceAfter=3)
    answer_style = ParagraphStyle('AnswerStyle', fontSize=12, spaceAfter=12, textColor='red')

    if include_answers:
        title += " (Answer Key)"
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 24))
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, question in enumerate(questions, 1):
            story.append(Paragraph(f"{i}.", question_style))
            story.append(process_question_content(question['question'], question_style, temp_dir))
            
            if 'options' in question and isinstance(question['options'], dict):
                for letter, option in question['options'].items():
                    option_text = f"{letter}. "
                    story.append(Paragraph(option_text, option_style))
                    story.append(process_question_content(option, option_style, temp_dir))
            
            if include_answers:
                if 'options' in question:
                    correct_answer = question['answer']
                    story.append(Paragraph(f"Answer: {correct_answer}", answer_style))
                else:
                    story.append(Paragraph(f"Answer: {question['answer']}", answer_style))
                
                if 'explanation' in question:
                    story.append(Paragraph("Explanation:", answer_style))
                    story.append(process_question_content(question['explanation'], answer_style, temp_dir))
            
            story.append(Spacer(1, 24))
    
    doc.build(story)
    
def validate_args(args, total_questions):
    if not os.path.exists(args.json_file):
        raise FileNotFoundError(f"JSON file not found: {args.json_file}")
    
    try:
        with open(args.json_file, 'r') as f:
            json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in file: {args.json_file}")

    if args.num_questions and args.num_questions > total_questions:
        raise ValueError(f"Requested number of questions ({args.num_questions}) exceeds available questions ({total_questions})")
    
    if args.pages and args.pages < 1:
        raise ValueError("Number of pages must be at least 1")
    
    if args.n_max and args.n_max < 1:
        raise ValueError("Maximum questions per worksheet must be at least 1")
    
    if args.num_questions and args.pages:
        if args.num_questions > args.pages * args.n_max:
            raise ValueError(f"Requested number of questions ({args.num_questions}) exceeds capacity of {args.pages} pages with {args.n_max} questions per page")

def distribute_questions(questions, num_pages, n_max):
    total_questions = len(questions)
    questions_per_page = min(math.ceil(total_questions / num_pages), n_max)
    return [questions[i:i+questions_per_page] for i in range(0, total_questions, questions_per_page)]