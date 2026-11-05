class ModelError(Exception):
    """Base model exception."""


class ConfigurationError(ModelError):
    """Invalid model configuration."""
