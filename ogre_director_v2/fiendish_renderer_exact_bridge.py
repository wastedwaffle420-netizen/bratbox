"""Install Fiendish's vendored LightmapRenderer methods without rewriting them.

The source of truth remains wotw_bratbox/vendor_full/ogre_shader_v5.py.  This
bridge extracts the renderer's own functions and constants with Python's AST,
then binds those exact function bodies to WotW's compatibility class.  WotW
keeps its surrounding game state; Fiendish owns lightmap motion and drawing.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path


_CONSTANTS = {
    "LIGHTMAP_PLAYBACK_CONTEXTS",
    "LIGHTMAP_STATE_MODIFIERS",
    "POSE_MODIFIER_ORIGINS",
}

_METHODS = {
    "set_playback_context",
    "configure_playback_modifiers",
    "_quantize_cell_offset",
    "_pose_modifier_origin",
    "_posture_modifier_offset",
    "_rhythm_impact_offset",
    "get_tree_suggested_pose",
    "set_pose",
    "trigger_hit",
    "trigger_shake",
    "trigger_flash",
    "set_dim",
    "update",
    "set_undulation_profile",
    "render",
}


def _named_assignment(node):
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if isinstance(target, ast.Name):
            return target.id
    return None


def install_exact_fiendish_renderer(namespace: dict, renderer_class: type) -> Path:
    vendor = Path(__file__).resolve().parent / "wotw_bratbox" / "vendor_full" / "ogre_shader_v5.py"
    tree = ast.parse(vendor.read_text(encoding="utf-8"), filename=str(vendor))

    constants = []
    renderer = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and _named_assignment(node) in _CONSTANTS:
            constants.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "LightmapRenderer":
            renderer = node
    if renderer is None:
        raise RuntimeError("Fiendish LightmapRenderer was not found")

    exact_methods = [copy.deepcopy(node) for node in renderer.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _METHODS]
    found = {node.name for node in exact_methods}
    missing = sorted(_METHODS - found)
    if missing:
        raise RuntimeError(f"Fiendish renderer methods missing: {missing}")

    # Preserve Fiendish's render body verbatim and insert only transparent WotW
    # compositor hooks at its two natural extension points: immediately before
    # Fiendish scales the source plate, and after Fiendish finishes drawing it.
    # No movement, phase, offset, pose, or raster statement is replaced.
    render_method = next(node for node in exact_methods if node.name == "render")
    pre_source = ast.parse("""
try:
    self.tactile_overlay.update_suckler_performance(
        intensity,
        int(getattr(self, 'momentum_combo', 0) or 0),
        int(getattr(self, 'momentum_misses', 0) or 0),
    )
    figure_source = self.tactile_overlay.deform_event_source_plate(figure_source, self.current_pose)
    figure_source = self._apply_hana_pelvic_variant(figure_source, self.current_pose)
except Exception:
    pass
""").body
    scale_index = None
    for index, statement in enumerate(render_method.body):
        if isinstance(statement, ast.If) and "lightmap.height > available_h" in ast.unparse(statement.test):
            scale_index = index
            break
    if scale_index is None:
        raise RuntimeError("Fiendish source-scale boundary was not found")
    render_method.body[scale_index:scale_index] = pre_source

    post_layers = ast.parse("""
try:
    self.tactile_overlay.render(
        scr, figure_lines, fig_x, start_y + fig_y_offset,
        self.current_pose, intensity,
        row_offset=lambda row: tuple(sum(v) for v in zip(
            self._posture_modifier_offset(row, len(figure_lines)),
            self._rhythm_impact_offset(row, len(figure_lines)),
        )),
    )
except Exception:
    pass
try:
    callback = getattr(self, 'participant_banner_callback', None)
    if callable(callback):
        callback()
except Exception:
    pass
""").body
    render_method.body.extend(post_layers)

    module = ast.fix_missing_locations(ast.Module(body=constants + exact_methods, type_ignores=[]))
    exact_namespace = dict(namespace)
    exec(compile(module, str(vendor), "exec"), exact_namespace)

    for name in _CONSTANTS:
        namespace[name] = exact_namespace[name]
    for name in _METHODS:
        setattr(renderer_class, name, exact_namespace[name])

    # Compatibility-only initialization. These are the fields in Fiendish's
    # __init__ used by its exact methods but absent from older WotW copies.
    original_init = renderer_class.__init__
    def compatible_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.state_phase = 0.0
        self.playback_context = "dialogue"
        self.state_energy = "safe"
        self.state_strength = 0.0
        self.rhythm_impact_t = 0.0
        self.rhythm_impact_duration = 0.0
        self.rhythm_impact_strength = 0.0
        self.rhythm_impact_dir = 1
        self.rhythm_impact_lane = ""
    renderer_class.__init__ = compatible_init
    renderer_class._exact_fiendish_renderer_source = str(vendor)
    return vendor
