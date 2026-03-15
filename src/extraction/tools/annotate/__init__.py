"""Interactive chunk quality annotation tool."""


def __getattr__(name):
    if name == "AnnotationApp":
        from .app import AnnotationApp
        return AnnotationApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AnnotationApp"]
