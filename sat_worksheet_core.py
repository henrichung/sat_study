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

def latex_to_image(latex_str, dpi=300):
    """Convert LaTeX string to inline PNG image data using mathtext rendering."""
    plt.rcParams.update({
        'backend': 'Agg',
        'text.usetex': False,  # Use mathtext for performance and compatibility
        'font.family': 'sans-serif',
        'font.serif': ['Computer Modern Roman'],
        'font.size': 10,
        'figure.dpi': dpi
    })
    
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.patch.set_alpha(0)
    ax.axis('off')
    
    # Wrap in math mode if needed
    if not latex_str.strip().startswith('\\'):
        latex_str = r'$' + latex_str + r'$'
    
    text = ax.text(0.5, 0.5, latex_str,
                   ha='center', va='center',
                   transform=ax.transAxes)
    
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bbox = text.get_window_extent(renderer)
    bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())
    
    img_data = io.BytesIO()
    try:
        fig.savefig(img_data, 
                    format='png',
                    bbox_inches=bbox_inches,
                    pad_inches=0.02,
                    transparent=True,
                    dpi=dpi)
        img_data.seek(0)
    finally:
        plt.close(fig)
    
    return img_data

def process_question_content(content, style, temp_dir, desired_height_pt=12):
    """Process question content, handling both text with inline LaTeX and images.
    Returns a Paragraph or Image flowable.
    """
    if isinstance(content, str):
        parts = content.split('$')
        if len(parts) > 1:  # Contains LaTeX parts
            markup = ""
            for i, part in enumerate(parts):
                if i % 2 == 0:
                    markup += escape(part)
                else:
                    try:
                        img_data = latex_to_image(part)
                        img_data.seek(0)
                        pil_img = PILImage.open(io.BytesIO(img_data.getvalue()))
                        width_px, height_px = pil_img.size
                        width_pt = (width_px / 300) * 72
                        height_pt = (height_px / 300) * 72
                        scale = desired_height_pt / height_pt
                        scaled_width = width_pt * scale
                        scaled_height = desired_height_pt
                        
                        img_filename = os.path.join(temp_dir, f"latex_{uuid.uuid4().hex}.png")
                        with open(img_filename, 'wb') as f:
                            f.write(img_data.getvalue())
    
                        markup += f'<img src="{img_filename}" valign="middle" width="{scaled_width}" height="{scaled_height}"/>'
                    except Exception as e:
                        print(f"Warning: LaTeX rendering failed for '{part}': {str(e)}")
                        markup += escape(f'${part}$')
            return Paragraph(markup, style)
        else:
            return Paragraph(escape(content), style)
    elif isinstance(content, dict):
        # Support for embedding images directly from a file path
        if 'image' in content:
            img_path = content['image']
            if os.path.exists(img_path):
                return Image(img_path, width=6*inch)
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