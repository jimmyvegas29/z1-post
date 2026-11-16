# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""Fusion side of the Z1 template: read one from an NC Program, find its machine and post in this computer's
libraries, and create an NC Program from it. Only officially supported API calls are used."""
from __future__ import annotations

import datetime
import re
from typing import Any, Optional

from adsk import cam

# Searched in this order; the first match wins.
_LOCATIONS = ("LocalLibraryLocation", "CloudLibraryLocation", "NetworkLibraryLocation", "HubLibraryLocation",
              "Fusion360LibraryLocation", "ExternalLibraryLocation")


def _libraries():
    manager = cam.CAMManager.get().libraryManager
    return manager.machineLibrary, manager.postLibrary


def _locations():
    return [getattr(cam.LibraryLocations, n) for n in _LOCATIONS if hasattr(cam.LibraryLocations, n)]


def capture(nc_program: Any, document_name: str = "") -> dict:
    """Template data from an NC Program that has a machine and a post processor."""
    machine = nc_program.machine
    post = nc_program.postConfiguration
    if machine is None or post is None:
        raise ValueError("The NC Program needs both a machine and a post processor.")
    settings = {}
    params = nc_program.postParameters
    for i in range(params.count):
        p = params.item(i)
        try:
            if p.isDeprecated or not p.isEditable:
                continue
            if p.expression != p.systemDefaultExpression:
                settings[p.name] = p.expression
        except RuntimeError:
            continue
    output_folder = ""
    try:
        output_folder = nc_program.parameters.itemByName("nc_program_output_folder").value.value
    except Exception:
        pass
    return {
        "machine": {"vendor": machine.vendor, "model": machine.model, "description": machine.description},
        "post": {"vendor": post.vendor, "description": post.description, "version": post.version,
                 "extension": post.extension},
        "post_settings": settings,
        "output_folder": output_folder or "",
        "saved": {"date": datetime.date.today().isoformat(), "program": nc_program.name,
                  "document": re.sub(r"\s+v\d+$", "", document_name or "")},
    }


def find_machine(template: dict) -> Optional[Any]:
    machine_library, _ = _libraries()
    want = template["machine"]
    for location in _locations():
        try:
            found = machine_library.createQuery(location, want.get("vendor", ""), want.get("model", "")).execute()
        except Exception:
            continue
        for m in found or []:
            if m.model == want.get("model"):
                return m
    return None


def find_post(template: dict) -> Optional[Any]:
    _, post_library = _libraries()
    want = template["post"]
    fallback = None
    for location in _locations():
        try:
            query = post_library.createQuery(location)
            if want.get("vendor"):
                query.vendor = want["vendor"]
            found = query.execute()
        except Exception:
            continue
        for p in found or []:
            if p.description != want.get("description"):
                continue
            if str(p.version) == str(want.get("version")):
                return p
            fallback = fallback or p     # same post, other version
    return fallback


def apply_post_settings(nc_program: Any, settings: dict) -> list[str]:
    """Set the saved post settings; returns the names that couldn't be set."""
    failed = []
    params = nc_program.postParameters
    for name, expression in settings.items():
        p = params.itemByName(name)
        if p is None:
            failed.append(name)
            continue
        try:
            p.expression = expression
        except RuntimeError:
            failed.append(name)
    try:
        nc_program.updatePostParameters(params)
    except RuntimeError:
        pass
    return failed


def create_nc_program(cam_product: Any, template: dict, name: str, operations: list,
                      machine: Any = None, post: Any = None) -> tuple[Any, list[str]]:
    """Add an NC Program to the document with the template's machine, post and settings.
    Pass the machine and post found earlier when possible: library lookups during the dialog's OK handler
    were seen to fail in Fusion with a stale "axisDefinition" error. Returns (the NC Program, names of
    settings that couldn't be set)."""
    machine = machine if machine is not None else find_machine(template)
    post = post if post is not None else find_post(template)
    if machine is None:
        raise ValueError(f"Machine '{template['machine']['model']}' isn't in this computer's machine libraries.")
    if post is None:
        raise ValueError(f"Post processor '{template['post']['description']}' isn't in this computer's post libraries.")
    nc_input = cam_product.ncPrograms.createInput()
    nc_input.displayName = name
    nc_input.operations = list(operations)
    nc_program = cam_product.ncPrograms.add(nc_input)
    nc_program.machine = machine          # this can also set the machine's own default post...
    nc_program.postConfiguration = post   # ...so the template's post is set after it
    failed = apply_post_settings(nc_program, template.get("post_settings") or {})
    return nc_program, failed
