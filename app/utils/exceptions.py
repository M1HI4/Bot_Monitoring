class AppError(Exception):
    """Base application error."""


class AccessDeniedError(AppError):
    """Raised when a Telegram user is not allowed to use the bot."""


class ConfigValidationError(AppError):
    """Raised when YAML configuration is invalid."""


class PrometheusRequestError(AppError):
    """Raised when Prometheus API request fails."""


class MetricUnavailableError(AppError):
    """Raised when a metric is not available for a target."""
