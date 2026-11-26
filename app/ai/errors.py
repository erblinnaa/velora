class AIProviderError(Exception):
    """Base error for provider and model communication failures."""


class AIProviderConfigurationError(AIProviderError):
    """The selected provider is not configured correctly."""


class AIProviderAuthenticationError(AIProviderError):
    """The provider rejected the configured credentials."""


class AIProviderRateLimitError(AIProviderError):
    """The provider quota or rate limit was exceeded."""


class AIProviderModelUnavailable(AIProviderError):
    """The configured model is unavailable for the provider."""


class AIProviderNetworkError(AIProviderError):
    """The provider could not be reached over the network."""


class AIProviderUnavailable(AIProviderError):
    """Raised when the configured local provider cannot be reached."""


class AIProviderTimeout(AIProviderError):
    """Raised when the provider takes longer than the configured timeout."""


class AIProviderResponseError(AIProviderError):
    """Raised when the provider returns an unusable response."""


class AIOutputValidationError(AIProviderError):
    """Raised when model output is not safe to use in the learning flow."""
