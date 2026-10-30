"""Shared finite limits; concurrency remains an explicit consumer choice."""
import math

DEFAULTS = dict(command_timeout=600, gate_timeout=1800, workers=1, deduplicate=True)


def resolve_profile(**overrides) -> dict:
    unknown = set(overrides) - set(DEFAULTS)
    if unknown:
        raise ValueError('unknown execution options: ' + ', '.join(sorted(unknown)))
    profile = dict(DEFAULTS, **{key: value for key, value in overrides.items() if value is not None})
    for key in ('command_timeout', 'gate_timeout'):
        value = profile[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError(key + ' must be positive and finite')
    if profile['gate_timeout'] <= profile['command_timeout']:
        raise ValueError('gate_timeout must exceed command_timeout')
    if type(profile['workers']) is not int or not 1 <= profile['workers'] <= 8:
        raise ValueError('workers must be an integer between 1 and 8')
    if type(profile['deduplicate']) is not bool:
        raise ValueError('deduplicate must be a boolean')
    return profile
