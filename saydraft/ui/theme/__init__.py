"""Install the generated Qt theme on the GUI thread before creating widgets."""

import logging


def install_theme(application, **kwargs):
    cached = getattr(application, "_saydraft_theme", None)
    if cached is not None and not cached.closed:
        return cached
    from .controller import ThemeController
    controller = None
    try:
        controller = ThemeController(application, **kwargs)
        controller.start()
        application._saydraft_theme = controller
        return controller
    except Exception:
        if controller is not None:
            controller.close()
        logging.getLogger(__name__).warning("Saydraft theme unavailable; using system appearance")
        return None
