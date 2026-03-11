"""
Conversion presets and custom parameter validation for vtracer.

Each preset is a dict of vtracer kwargs. Custom params are validated
against CUSTOM_PARAM_RANGES and merged onto the default preset.
"""
from fastapi import HTTPException

from modules.config import DEFAULT_PRESET

# vtracer conversion parameter presets (low speckle = more detail, higher precision = slower)
PRESETS = {
    'high_quality': {
        'colormode': 'color',
        'mode': 'spline',
        'filter_speckle': 2,
        'color_precision': 8,
        'layer_difference': 8,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 20,
        'splice_threshold': 45,
        'path_precision': 5,
    },
    'balanced': {
        'colormode': 'color',
        'mode': 'spline',
        'filter_speckle': 4,
        'color_precision': 6,
        'layer_difference': 16,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 10,
        'splice_threshold': 45,
        'path_precision': 3,
    },
    'fast': {
        'colormode': 'color',
        'mode': 'spline',
        'filter_speckle': 8,
        'color_precision': 4,
        'layer_difference': 32,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 5,
        'splice_threshold': 45,
        'path_precision': 2,
    },
}

# Allowed custom parameter ranges for validation.
# 'enum' type restricts to a set of string values; 'int'/'float' enforce numeric bounds.
CUSTOM_PARAM_RANGES = {
    'colormode': {'type': 'enum', 'values': ['color', 'binary']},
    'mode': {'type': 'enum', 'values': ['spline', 'polygon', 'none']},
    'filter_speckle': {'type': 'int', 'min': 1, 'max': 128},
    'color_precision': {'type': 'int', 'min': 1, 'max': 8},
    'layer_difference': {'type': 'int', 'min': 1, 'max': 256},
    'corner_threshold': {'type': 'int', 'min': 0, 'max': 180},
    'length_threshold': {'type': 'float', 'min': 0.0, 'max': 100.0},
    'max_iterations': {'type': 'int', 'min': 1, 'max': 50},
    'splice_threshold': {'type': 'int', 'min': 0, 'max': 180},
    'path_precision': {'type': 'int', 'min': 1, 'max': 10},
}


def validate_custom_params(params: dict) -> dict:
    """Validate and sanitize custom conversion parameters.

    Starts from the default preset values, then overrides with
    validated user-supplied params. Unknown keys are silently ignored.

    Returns:
        Validated params dict ready for vtracer

    Raises:
        HTTPException: If any parameter value is invalid
    """
    base = dict(PRESETS[DEFAULT_PRESET])
    for key, value in params.items():
        if key not in CUSTOM_PARAM_RANGES:
            continue  # Ignore unknown keys
        spec = CUSTOM_PARAM_RANGES[key]
        if spec['type'] == 'enum':
            if value not in spec['values']:
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Invalid value for {key}: {value}. "
                            f"Allowed: {spec['values']}", 'code': 'INVALID_PARAM'}
                )
            base[key] = value
        elif spec['type'] == 'int':
            try:
                val = int(value)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Invalid value for {key}: must be integer",
                            'code': 'INVALID_PARAM'}
                )
            if val < spec['min'] or val > spec['max']:
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Value for {key} must be between "
                            f"{spec['min']} and {spec['max']}", 'code': 'INVALID_PARAM'}
                )
            base[key] = val
        elif spec['type'] == 'float':
            try:
                val = float(value)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Invalid value for {key}: must be number",
                            'code': 'INVALID_PARAM'}
                )
            if val < spec['min'] or val > spec['max']:
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Value for {key} must be between "
                            f"{spec['min']} and {spec['max']}", 'code': 'INVALID_PARAM'}
                )
            base[key] = val
    return base
