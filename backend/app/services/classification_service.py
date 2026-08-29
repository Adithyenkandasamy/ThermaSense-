"""Classification service wrapper."""

from app.services.classifier import classify, classify_batch

__all__ = ["classify", "classify_batch"]
