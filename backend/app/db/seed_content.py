"""
Demo seed data for lessons + resources.

DISABLED BY DEFAULT: admins enter real content through the Resources / Lessons
admin pages, so we no longer auto-populate the DB with demo rows. The sample
data below is kept only as an optional fixture — set the env var
``SEED_DEMO_CONTENT=true`` to re-enable seeding an empty DB with it.
"""
import logging
import os

from app.db import models

log = logging.getLogger("cbt")


_LESSONS = [
    {"title": "Managing Stress Effectively",
     "description": "Understand and control stress in everyday life",
     "category": "Stress Management", "level": "basic", "duration": "15 min",
     "status": "published", "author": "Admin",
     "tags": ["stress", "relaxation"],
     "objectives": ["Recognize stress triggers",
                    "Apply quick calming techniques"]},
    {"title": "Positive Thinking Every Day",
     "description": "Train a positive mindset to improve your emotions",
     "category": "Positive Thinking", "level": "basic", "duration": "12 min",
     "status": "published", "author": "Minh Anh",
     "tags": ["mindset", "emotion control"]},
    {"title": "Mindfulness in the Present",
     "description": "Practice mindfulness to live fully in the moment",
     "category": "Mindfulness", "level": "intermediate", "duration": "18 min",
     "status": "published", "author": "Trần Quang Huy",
     "tags": ["mindfulness"]},
    {"title": "4-7-8 Relaxation Breathing",
     "description": "The 4-7-8 breathing technique to ease anxiety quickly",
     "category": "Breathing & Relaxation", "level": "basic",
     "duration": "8 min", "status": "published", "author": "Lê Thanh Tâm",
     "tags": ["breathing", "anxiety"]},
    {"title": "Building Healthy Habits",
     "description": "Step by step toward lasting positive habits",
     "category": "Habits", "level": "intermediate", "duration": "20 min",
     "status": "draft", "author": "Phạm Gia Bảo", "tags": ["habits"]},
    {"title": "Facing Anxiety",
     "description": "Recognize and overcome anxiety sustainably",
     "category": "Stress Management", "level": "intermediate",
     "duration": "16 min", "status": "draft", "author": "Vũ Thùy Linh",
     "tags": ["anxiety"]},
    {"title": "Positive Communication Skills",
     "description": "Communicate effectively and build healthy relationships",
     "category": "Social Skills", "level": "advanced", "duration": "22 min",
     "status": "published", "author": "Hoàng Nam", "tags": ["social"]},
    {"title": "Sleep Well, Live Well",
     "description": "Habits to improve sleep and restore energy",
     "category": "Mental Wellness", "level": "basic", "duration": "14 min",
     "status": "published", "author": "Đặng Thu Trang", "tags": ["sleep"]},
]


_RESOURCES = [
    {"type": "Audio", "title": "5 Minutes of Deep Breathing Daily",
     "description": "A guided deep-breathing practice to relieve stress quickly.",
     "category": "Stress Relief", "duration": "05:23", "status": "published",
     "owner": "Trần Quang Huy", "tags": ["breathing", "stress"]},
    {"type": "Article", "title": "Understanding Anxiety and How to Manage It",
     "description": "An article covering the basics of anxiety and how to control it.",
     "category": "Psychology Knowledge", "duration": "", "status": "published",
     "owner": "Lê Thanh Tâm", "tags": ["anxiety"]},
    {"type": "Video", "title": "Mindfulness Meditation for Beginners",
     "description": "A 10-minute mindfulness meditation guide for beginners.",
     "category": "Mindfulness", "duration": "10:12", "status": "published",
     "owner": "Vũ Thùy Linh", "tags": ["mindfulness", "meditation"]},
    {"type": "Article", "title": "Emergency Support Hotline",
     "description": "24/7 contact information for emergency situations.",
     "category": "Emergency Support", "duration": "", "status": "urgent",
     "urgent": True, "owner": "Phạm Gia Bảo",
     "tags": ["urgent", "hotline", "support", "24/7"]},
    {"type": "CBT Tool", "title": "Thought Journal (CBT)",
     "description": "A tool to record and analyze thoughts using the CBT method.",
     "category": "CBT", "duration": "", "status": "published",
     "owner": "Hoàng Nam", "tags": ["cbt", "journal"]},
    {"type": "Article", "title": "Managing Sleep Effectively",
     "description": "Tips and habits to improve sleep quality every day.",
     "category": "Mental Wellness", "duration": "", "status": "update",
     "owner": "Đặng Thu Trang", "tags": ["sleep"]},
    {"type": "Video", "title": "Building Self-Confidence",
     "description": "A video guide on building and maintaining self-confidence.",
     "category": "Personal Development", "duration": "08:45",
     "status": "published", "owner": "Nguyễn Hoài An", "tags": ["confidence"]},
]


def seed_content(db) -> None:
    """Insert demo lessons/resources only if the tables are empty.

    No-op unless ``SEED_DEMO_CONTENT=true`` — production/real deployments start
    with empty content tables and admins add the real material themselves.
    """
    if os.getenv("SEED_DEMO_CONTENT", "false").strip().lower() not in ("1", "true", "yes"):
        return
    if db.query(models.Lesson).first() is None:
        for row in _LESSONS:
            db.add(models.Lesson(**row))
        log.info("Seeded %d lessons", len(_LESSONS))
    if db.query(models.Resource).first() is None:
        for row in _RESOURCES:
            db.add(models.Resource(**row))
        log.info("Seeded %d resources", len(_RESOURCES))
    db.flush()
