"""Label template configuration: dimensions, fields, positions, font sizes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List


@dataclass
class FieldDef:
    """One printable field on the label."""

    field_key: str       # "case_id" | "tube_id" | "position" | custom metadata key
    display_name: str    # prefix text printed before the value, e.g. "Case"
    x_mm: float          # left offset in mm from label left edge
    y_mm: float          # top offset in mm from label top edge
    font_size_pt: int    # point size for this field
    enabled: bool        # whether this field is printed at all
    show_prefix: bool = True  # whether to prepend display_name: before the value


@dataclass
class LabelConfig:
    """Full label template (size + list of fields)."""

    label_width_mm: float
    label_height_mm: float
    fields: List[FieldDef]

    # -- Defaults ------------------------------------------------------------

    @staticmethod
    def default_config() -> "LabelConfig":
        return LabelConfig(
            label_width_mm=36.0,
            label_height_mm=20.0,
            fields=[
                FieldDef("case_id",  "Case",     x_mm=2.0, y_mm=2.0,  font_size_pt=9, enabled=True),
                FieldDef("tube_id",  "Tube",     x_mm=2.0, y_mm=8.0,  font_size_pt=7, enabled=True),
                FieldDef("position", "Position", x_mm=2.0, y_mm=13.5, font_size_pt=7, enabled=True),
            ],
        )

    # -- Serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "label_width_mm": self.label_width_mm,
            "label_height_mm": self.label_height_mm,
            "fields": [
                {
                    "field_key":    fdef.field_key,
                    "display_name": fdef.display_name,
                    "x_mm":         fdef.x_mm,
                    "y_mm":         fdef.y_mm,
                    "font_size_pt": fdef.font_size_pt,
                    "enabled":      fdef.enabled,
                    "show_prefix":  fdef.show_prefix,
                }
                for fdef in self.fields
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LabelConfig":
        fields = [
            FieldDef(
                field_key=str(f["field_key"]),
                display_name=str(f.get("display_name", f["field_key"])),
                x_mm=float(f.get("x_mm", 2.0)),
                y_mm=float(f.get("y_mm", 2.0)),
                font_size_pt=int(f.get("font_size_pt", 8)),
                enabled=bool(f.get("enabled", True)),
                show_prefix=bool(f.get("show_prefix", True)),
            )
            for f in data.get("fields", [])
        ]
        return cls(
            label_width_mm=float(data.get("label_width_mm", 36.0)),
            label_height_mm=float(data.get("label_height_mm", 20.0)),
            fields=fields,
        )

    # Backward-compat single-config file methods
    def save_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(self.to_dict(), fp, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "LabelConfig":
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return cls.from_dict(data)


class LabelTemplateStore:
    """Manages multiple named label templates with one active at a time."""

    DEFAULT_NAME = "Default"

    def __init__(
        self,
        templates: "dict[str, LabelConfig] | None" = None,
        active_name: str | None = None,
    ) -> None:
        if templates:
            self.templates: dict[str, LabelConfig] = dict(templates)
        else:
            self.templates = {self.DEFAULT_NAME: LabelConfig.default_config()}

        if active_name and active_name in self.templates:
            self.active_name: str = active_name
        else:
            self.active_name = next(iter(self.templates))

    @property
    def active(self) -> LabelConfig:
        return self.templates[self.active_name]

    def save_to_file(self, path: str) -> None:
        data = {
            "active": self.active_name,
            "templates": {
                name: config.to_dict()
                for name, config in self.templates.items()
            },
        }
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "LabelTemplateStore":
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        # New multi-template format
        if "templates" in data:
            templates = {
                name: LabelConfig.from_dict(cfg)
                for name, cfg in data["templates"].items()
            }
            if not templates:
                return cls()
            active_name = data.get("active", next(iter(templates)))
            return cls(templates=templates, active_name=active_name)

        # Legacy single-config format � wrap in store
        config = LabelConfig.from_dict(data)
        return cls(templates={cls.DEFAULT_NAME: config}, active_name=cls.DEFAULT_NAME)
