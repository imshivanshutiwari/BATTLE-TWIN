"""NVG green-on-black theme for C2 dashboard."""

NVG_THEME = {
    "bg": "#060a04",
    "panel_bg": "#0d1117",
    "border": "#00ff41",
    "text": "#00ff41",
    "text_dim": "#00cc33",
    "accent": "#88ff00",
    "threat": "#ff4400",
    "friendly": "#00ccff",
    "hostile": "#ff3333",
    "unknown": "#ffcc00",
    "grid": "#003300",
    "highlight": "#39ff14",
}

FONT_FAMILY = "'Courier New', 'Lucida Console', monospace"

PLOTLY_TEMPLATE = {
    "paper_bgcolor": NVG_THEME["panel_bg"],
    "plot_bgcolor": NVG_THEME["bg"],
    "font": {"color": NVG_THEME["text"], "family": FONT_FAMILY, "size": 10},
    "margin": {"l": 30, "r": 10, "t": 25, "b": 20},
    "xaxis": {"gridcolor": NVG_THEME["grid"], "zerolinecolor": NVG_THEME["grid"]},
    "yaxis": {"gridcolor": NVG_THEME["grid"], "zerolinecolor": NVG_THEME["grid"]},
}

SEVERITY_COLORS = {
    "ROUTINE": "#888888",
    "PRIORITY": "#00ccff",
    "IMMEDIATE": "#ffcc00",
    "FLASH": "#ff6600",
    "OVERRIDE": "#ff0000",
}

UNIT_SYMBOLS = {
    "friendly": {"shape": "circle", "color": NVG_THEME["friendly"]},
    "hostile": {"shape": "triangle-up", "color": NVG_THEME["hostile"]},
    "unknown": {"shape": "square", "color": NVG_THEME["unknown"]},
}

PANEL_STYLE = {
    "backgroundColor": NVG_THEME["panel_bg"],
    "border": f"1px solid {NVG_THEME['border']}",
    "borderRadius": "4px",
    "padding": "10px",
    "marginBottom": "8px",
}

HEADER_STYLE = {
    "color": NVG_THEME["accent"],
    "fontFamily": FONT_FAMILY,
    "fontSize": "11px",
    "textTransform": "uppercase",
    "letterSpacing": "1px",
    "margin": "0 0 8px 0",
}


if __name__ == "__main__":
    print(f"Theme colors: {len(NVG_THEME)} defined")
    print(f"Severity levels: {list(SEVERITY_COLORS.keys())}")
    print("theme.py OK")
