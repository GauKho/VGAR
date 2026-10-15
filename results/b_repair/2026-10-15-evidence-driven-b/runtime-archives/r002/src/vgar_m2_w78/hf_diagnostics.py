"""Observe the pinned HF decoder without changing generation arguments or tensors."""
from dataclasses import asdict, is_dataclass
import inspect
import json

from .diagnostics import exception_details
from .evidence import digest


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    if hasattr(value, 'detach') and hasattr(value, 'tolist'):
        return dict(tensor_values=value.detach().cpu().tolist(), dtype=str(value.dtype), device=str(value.device))
    if is_dataclass(value):
        return _json_value(asdict(value))
    return dict(python_type=type(value).__name__, representation=repr(value))


def _config(config):
    return _json_value(config.to_dict()) if config is not None else None


def _tensor_summary(tensor):
    if tensor is None:
        return None
    values = tensor.detach().cpu().tolist()
    def flattened(value):
        if isinstance(value, list):
            for item in value:
                yield from flattened(item)
        else:
            yield value
    flat = list(flattened(values))
    return dict(shape=list(tensor.shape), dtype=str(tensor.dtype), device=str(tensor.device),
        elements=len(flat), zeros=sum(v == 0 for v in flat), ones=sum(v == 1 for v in flat),
        binary=all(v in (0, 1) for v in flat), sha256=digest(json.dumps(values, separators=(',', ':'))))


def generate_observed(model, inputs, settings, overrides, emit):
    """Return (unchanged generate result, diagnostics); emit snapshots before decoding.

    Transformers 4.57.6 calls self._get_logits_processor after length/cache/mask
    preparation, then dispatches the decoder on type(self), not the instance.
    The observer records actual prepared config and mask at this pre-decode boundary, rather
    than treating checkpoint defaults as effective settings. No explicit mask,
    padding, generation option or random state is introduced by this observer.
    """
    diagnostic = dict(status='NOT_RUN', phase='before_generate',
        checkpoint_generation_config=_config(model.generation_config),
        supplied_generation_config=_config(settings), generate_overrides=_json_value(overrides),
        input_ids=_tensor_summary(inputs), attention_mask_supplied_by_host='attention_mask' in overrides,
        effective_observed=False, effective_generation_config=None, attention_mask=None,
        capture_boundary='pre_decode:_get_logits_processor', exception=None)
    original = getattr(model, '_get_logits_processor', None)
    supported = callable(original)
    diagnostic['capture_supported'] = supported
    emit(diagnostic)
    had_instance_attribute = '_get_logits_processor' in vars(model)
    previous = vars(model).get('_get_logits_processor')

    def observed(*args, **kwargs):
        try:
            bound = inspect.signature(original).bind(*args, **kwargs).arguments
            extra = bound.get('model_kwargs', {})
            config = bound.get('generation_config')
            mask = bound.get('attention_mask', extra.get('attention_mask'))
            diagnostic.update(effective_observed=config is not None,
                effective_generation_config=_config(config), attention_mask=_tensor_summary(mask),
                phase='pre_decode')
        except (TypeError, ValueError) as error:
            # Unsupported framework signature is reported, not silently inferred.
            diagnostic.update(capture_exception=exception_details(error), phase='pre_decode')
        emit(diagnostic)
        return original(*args, **kwargs)

    if supported:
        model._get_logits_processor = observed
    try:
        output = model.generate(inputs, generation_config=settings, **overrides)
        diagnostic.update(status='PASS', phase='complete')
        emit(diagnostic)
        return output, diagnostic
    except BaseException as error:
        diagnostic.update(status='ERROR', phase='error', exception=exception_details(error))
        emit(diagnostic)
        raise
    finally:
        if supported:
            if had_instance_attribute:
                model._get_logits_processor = previous
            else:
                delattr(model, '_get_logits_processor')
