"""
This file contains logic for managing custom event loops;
this is needed since pygeoapi doesn't internally support async
in the upstream so we need to create and manage an event loop.
This allows us to use async code within pygeoapi and flask
without hard forking internals

In order to use the event loop, this file must be imported
and ran before any async code is run
"""

import asyncio
import importlib
import os
from typing import Callable, Optional
import logging

LOGGER = logging.getLogger(__name__)

# The module in which the event loop can be found
_CUSTOM_EVENT_LOOP_MODULE: Optional[str] = os.getenv(
    "PYGEOAPI_CUSTOM_EVENT_LOOP_MODULE"
)
# The function that can be called for retrieving the event loop
_CUSTOM_EVENT_LOOP_GETTER: Optional[str] = os.getenv(
    "PYGEOAPI_CUSTOM_EVENT_LOOP_GETTER"
)

# A function that can be called to get the custom event loop; if it is not
# defined then there is no custom event loop
get_custom_event_loop: Optional[Callable[[], asyncio.AbstractEventLoop]] = None

# Check that both are defined
if (_CUSTOM_EVENT_LOOP_GETTER and not _CUSTOM_EVENT_LOOP_MODULE) or (
    not _CUSTOM_EVENT_LOOP_GETTER and _CUSTOM_EVENT_LOOP_MODULE
):
    raise ValueError(
        "env vars PYGEOAPI_CUSTOM_EVENT_LOOP_MODULE and "
        "PYGEOAPI_CUSTOM_EVENT_LOOP_GETTER must be defined together"
        "or not defined at all"
    )

if _CUSTOM_EVENT_LOOP_MODULE and _CUSTOM_EVENT_LOOP_GETTER:
    try:
        event_loop_module = importlib.import_module(_CUSTOM_EVENT_LOOP_MODULE)
    except ImportError as err:
        raise ImportError(
            f"Unable to import custom event loop module"
            f" {_CUSTOM_EVENT_LOOP_MODULE} with error: {err}"
        )

    try:
        get_custom_event_loop = \
            getattr(event_loop_module, _CUSTOM_EVENT_LOOP_GETTER)
        LOGGER.info(
            f"Found custom event loop at "
            f"{_CUSTOM_EVENT_LOOP_MODULE}.{_CUSTOM_EVENT_LOOP_GETTER}"
        )
    except AttributeError as err:
        raise AttributeError(
            f"Unable to find custom event loop getter"
            f" {_CUSTOM_EVENT_LOOP_GETTER} in module"
            f" {_CUSTOM_EVENT_LOOP_MODULE}"
            f" with error: {err}"
        )
