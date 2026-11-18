"""Universal Screen Profile Data Model for SUSCRCPY 2.1.

Defines the screen profile data structure, dimensions validation, aspect ratio math,
and Android window size class calculation.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

VALID_CATEGORIES = [
    "smartphone",
    "tablet",
    "foldable",
    "wearable",
    "laptop",
    "monitor",
    "television",
    "gaming",
    "automotive",
    "kiosk",
    "xr",
    "ereader",
    "custom",
]

CATEGORY_LABELS = {
    "smartphone": "Smartphones",
    "tablet": "Tablets",
    "foldable": "Foldables",
    "wearable": "Wearables",
    "laptop": "Laptops",
    "monitor": "Desktop Monitors",
    "television": "TV & Streaming",
    "gaming": "Gaming Handhelds",
    "automotive": "Automotive Displays",
    "kiosk": "Kiosks & Signage",
    "xr": "XR & Spatial Displays",
    "ereader": "E-Readers",
    "custom": "Custom Profiles",
}

# Android Window Size Class breakpoints (in dp)
# Width: Compact (< 600 dp), Medium (600 - 839 dp), Expanded (840 - 1199 dp), Large (1200 - 1599 dp), Extra Large (>= 1600 dp)
# Height: Compact (< 480 dp), Medium (480 - 899 dp), Expanded (>= 900 dp)
WIDTH_SIZE_CLASSES = [
    (0, 599, "Compact (< 600 dp)"),
    (600, 839, "Medium (600-839 dp)"),
    (840, 1199, "Expanded (840-1199 dp)"),
    (1200, 1599, "Large (1200-1599 dp)"),
    (1600, 999999, "Extra Large (>= 1600 dp)"),
]

HEIGHT_SIZE_CLASSES = [
    (0, 479, "Compact (< 480 dp)"),
    (480, 899, "Medium (480-899 dp)"),
    (900, 999999, "Expanded (>= 900 dp)"),
]


@dataclass
class Resolution:
    width_px: int
    height_px: int

    def validate(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError(f"Resolution dimensions must be positive integers, got {self.width_px}x{self.height_px}")


@dataclass
class AspectRatio:
    width: int
    height: int

    @property
    def label(self) -> str:
        return f"{self.width}:{self.height}"


@dataclass
class Density:
    dpi: Optional[int] = None
    scale_factor: Optional[float] = None


@dataclass
class LogicalViewport:
    width_dp: Optional[int] = None
    height_dp: Optional[int] = None


@dataclass
class Cutout:
    type: str  # "punch_hole", "notch", "dynamic_island", "pill"
    x: int
    y: int
    width: int
    height: int
    radius: int = 0


@dataclass
class SafeAreas:
    top: int = 0
    bottom: int = 0
    left: int = 0
    right: int = 0


@dataclass
class FoldableInfo:
    enabled: bool = False
    posture: Optional[str] = None  # "closed", "unfolded", "half_open", "tabletop"
    hinge: Optional[Dict[str, Any]] = None  # position, width, orientation
    display_mode: Optional[str] = None  # "cover", "inner", "dual"


@dataclass
class XRInfo:
    enabled: bool = False
    per_eye_width_px: Optional[int] = None
    per_eye_height_px: Optional[int] = None
    fov_deg: Optional[float] = None
    ipd_mm: Optional[float] = None
    stereo_mode: Optional[str] = None  # "side_by_side", "monoscopic"
    distortion_profile: Optional[str] = None


@dataclass
class DualScreenInfo:
    enabled: bool = False
    secondary_width_px: Optional[int] = None
    secondary_height_px: Optional[int] = None
    layout: Optional[str] = None  # "horizontal", "vertical"


@dataclass
class ScreenProfile:
    id: str
    category: str
    platform: str
    manufacturer: str
    model: str
    screen_name: str
    resolution: Resolution
    aspect_ratio: AspectRatio
    density: Density = field(default_factory=Density)
    logical_viewport: LogicalViewport = field(default_factory=LogicalViewport)
    orientation: str = "portrait"  # "portrait", "landscape", "reverse_portrait", "reverse_landscape", "auto"
    shape: str = "rectangle"  # "rectangle", "round", "pill", "curved"
    cutouts: List[Cutout] = field(default_factory=list)
    safe_areas: SafeAreas = field(default_factory=SafeAreas)
    foldable: FoldableInfo = field(default_factory=FoldableInfo)
    xr: XRInfo = field(default_factory=XRInfo)
    dual_screen: DualScreenInfo = field(default_factory=DualScreenInfo)
    refresh_rate_hz: Optional[int] = None
    profile_source: str = "generic"  # "verified", "generic", "custom"
    verified: bool = False
    notes: Optional[str] = None

    def __post_init__(self):
        # Auto-calculate aspect ratio if not explicitly set
        if self.aspect_ratio.width == 0 or self.aspect_ratio.height == 0:
            self.aspect_ratio = self.calculate_aspect_ratio(
                self.resolution.width_px, self.resolution.height_px
            )

        # Auto-calculate logical viewport dp if density scale is available
        if self.logical_viewport.width_dp is None and self.density.scale_factor:
            self.logical_viewport.width_dp = round(self.resolution.width_px / self.density.scale_factor)
            self.logical_viewport.height_dp = round(self.resolution.height_px / self.density.scale_factor)
        elif self.logical_viewport.width_dp is None and self.density.dpi:
            scale = self.density.dpi / 160.0
            self.logical_viewport.width_dp = round(self.resolution.width_px / scale)
            self.logical_viewport.height_dp = round(self.resolution.height_px / scale)

    @staticmethod
    def calculate_aspect_ratio(width_px: int, height_px: int) -> AspectRatio:
        """Calculate simplified aspect ratio using Greatest Common Divisor (GCD)."""
        if width_px <= 0 or height_px <= 0:
            return AspectRatio(width=1, height=1)
        gcd = math.gcd(width_px, height_px)
        rw = width_px // gcd
        rh = height_px // gcd

        # Simplify common standard fractions if needed (e.g. 8:5 -> 16:10, 39:18 -> 19.5:9)
        if rw == 8 and rh == 5:
            return AspectRatio(width=16, height=10)
        if rw == 5 and rh == 8:
            return AspectRatio(width=10, height=16)

        return AspectRatio(width=rw, height=rh)

    def get_effective_dimensions(self, current_orientation: Optional[str] = None) -> Tuple[int, int]:
        """Return (width, height) accounting for rotation/orientation."""
        orient = current_orientation or self.orientation
        w, h = self.resolution.width_px, self.resolution.height_px
        if orient in ("landscape", "reverse_landscape"):
            return max(w, h), min(w, h)
        elif orient in ("portrait", "reverse_portrait"):
            return min(w, h), max(w, h)
        return w, h

    def get_window_size_classes(self) -> Tuple[str, str]:
        """Compute Android Responsive Window Size Class for Width and Height."""
        dp_w = self.logical_viewport.width_dp
        dp_h = self.logical_viewport.height_dp

        # Fallback to estimating with standard mdpi scale (1.0) if missing
        if dp_w is None:
            scale = self.density.scale_factor or 2.0
            dp_w = round(self.resolution.width_px / scale)
            dp_h = round(self.resolution.height_px / scale)

        width_class = "Compact (< 600 dp)"
        for low, high, label in WIDTH_SIZE_CLASSES:
            if low <= dp_w <= high:
                width_class = label
                break

        height_class = "Medium (480-899 dp)"
        for low, high, label in HEIGHT_SIZE_CLASSES:
            if low <= dp_h <= high:
                height_class = label
                break

        return width_class, height_class

    def validate(self) -> None:
        """Validate profile integrity and required constraints."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Profile 'id' must be a non-empty string.")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{self.category}'. Must be one of: {VALID_CATEGORIES}")
        if not self.model:
            raise ValueError("Profile 'model' must be defined.")
        self.resolution.validate()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to JSON-compatible dictionary."""
        d: Dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "platform": self.platform,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "screen_name": self.screen_name,
            "resolution": asdict(self.resolution),
            "aspect_ratio": asdict(self.aspect_ratio),
            "density": asdict(self.density),
            "logical_viewport": asdict(self.logical_viewport),
            "orientation": self.orientation,
            "shape": self.shape,
            "cutouts": [asdict(c) for c in self.cutouts],
            "safe_areas": asdict(self.safe_areas),
            "foldable": asdict(self.foldable),
            "xr": asdict(self.xr),
            "dual_screen": asdict(self.dual_screen),
            "refresh_rate_hz": self.refresh_rate_hz,
            "profile_source": self.profile_source,
            "verified": self.verified,
        }
        if self.notes:
            d["notes"] = self.notes
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScreenProfile:
        """Construct ScreenProfile from dictionary with validation."""
        res_data = data.get("resolution", {})
        resolution = Resolution(
            width_px=int(res_data.get("width_px", 1080)),
            height_px=int(res_data.get("height_px", 1920)),
        )

        ar_data = data.get("aspect_ratio", {})
        aspect_ratio = AspectRatio(
            width=int(ar_data.get("width", 0)),
            height=int(ar_data.get("height", 0)),
        )

        den_data = data.get("density", {})
        density = Density(
            dpi=den_data.get("dpi"),
            scale_factor=den_data.get("scale_factor"),
        )

        lv_data = data.get("logical_viewport", {})
        logical_viewport = LogicalViewport(
            width_dp=lv_data.get("width_dp"),
            height_dp=lv_data.get("height_dp"),
        )

        cutouts_data = data.get("cutouts", [])
        cutouts = [
            Cutout(
                type=c.get("type", "notch"),
                x=int(c.get("x", 0)),
                y=int(c.get("y", 0)),
                width=int(c.get("width", 0)),
                height=int(c.get("height", 0)),
                radius=int(c.get("radius", 0)),
            )
            for c in cutouts_data
        ]

        sa_data = data.get("safe_areas", {})
        safe_areas = SafeAreas(
            top=int(sa_data.get("top", 0)),
            bottom=int(sa_data.get("bottom", 0)),
            left=int(sa_data.get("left", 0)),
            right=int(sa_data.get("right", 0)),
        )

        f_data = data.get("foldable", {})
        foldable = FoldableInfo(
            enabled=bool(f_data.get("enabled", False)),
            posture=f_data.get("posture"),
            hinge=f_data.get("hinge"),
            display_mode=f_data.get("display_mode"),
        )

        xr_data = data.get("xr", {})
        xr = XRInfo(
            enabled=bool(xr_data.get("enabled", False)),
            per_eye_width_px=xr_data.get("per_eye_width_px"),
            per_eye_height_px=xr_data.get("per_eye_height_px"),
            fov_deg=xr_data.get("fov_deg"),
            ipd_mm=xr_data.get("ipd_mm"),
            stereo_mode=xr_data.get("stereo_mode"),
            distortion_profile=xr_data.get("distortion_profile"),
        )

        ds_data = data.get("dual_screen", {})
        dual_screen = DualScreenInfo(
            enabled=bool(ds_data.get("enabled", False)),
            secondary_width_px=ds_data.get("secondary_width_px"),
            secondary_height_px=ds_data.get("secondary_height_px"),
            layout=ds_data.get("layout"),
        )

        profile = cls(
            id=str(data.get("id", "")),
            category=str(data.get("category", "smartphone")),
            platform=str(data.get("platform", "android")),
            manufacturer=str(data.get("manufacturer", "Generic")),
            model=str(data.get("model", "Device")),
            screen_name=str(data.get("screen_name", "Main Display")),
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            density=density,
            logical_viewport=logical_viewport,
            orientation=str(data.get("orientation", "portrait")),
            shape=str(data.get("shape", "rectangle")),
            cutouts=cutouts,
            safe_areas=safe_areas,
            foldable=foldable,
            xr=xr,
            dual_screen=dual_screen,
            refresh_rate_hz=data.get("refresh_rate_hz"),
            profile_source=str(data.get("profile_source", "generic")),
            verified=bool(data.get("verified", False)),
            notes=data.get("notes"),
        )
        profile.validate()
        return profile
