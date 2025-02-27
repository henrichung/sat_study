#!/usr/bin/env python3
"""
Question data models for SAT Study application
"""
from dataclasses import dataclass
from typing import Optional, List, Dict
import uuid


@dataclass
class QuestionOption:
    text: str
    image: Optional[str] = None


@dataclass
class QuestionExplanation:
    text: str


@dataclass
class QuestionContent:
    text: str
    image: Optional[str] = None


@dataclass
class Question:
    content: QuestionContent
    options: dict[str, QuestionOption]
    answer: str
    difficulty: str
    tags: List[str]
    explanation: QuestionExplanation
    uid: str = None

    def __post_init__(self):
        if self.uid is None:
            self.uid = str(uuid.uuid4())

    @property
    def text(self) -> str:
        return self.content.text

    @property
    def image(self) -> Optional[str]:
        return self.content.image

    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        options = {k: QuestionOption(**v) for k, v in data.get('options', {}).items()}
        explanation = QuestionExplanation(**data.get('explanation', {'text': ''}))
        content = QuestionContent(
            text=data.get('question', {}).get('text', ''),
            image=data.get('question', {}).get('image')
        )
        question_data = {
            'content': content,
            'options': options,
            'answer': data.get('answer', ''),
            'difficulty': data.get('difficulty', ''),
            'tags': data.get('tags', []),
            'explanation': explanation,
            'uid': data.get('uid')
        }
        return cls(**question_data)

    def to_dict(self) -> dict:
        return {
            'question': {
                'text': self.content.text,
                'image': self.content.image
            },
            'options': {
                k: {'text': v.text, 'image': v.image}
                for k, v in self.options.items()
            },
            'answer': self.answer,
            'difficulty': self.difficulty,
            'tags': self.tags,
            'explanation': {
                'text': self.explanation.text
            },
            'uid': self.uid
        }