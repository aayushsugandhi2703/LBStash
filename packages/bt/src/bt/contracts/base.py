"""Base model, field types and validation helpers every contract uses.

* JSON keys are camelCase, Python attributes snake_case (both validate); unknown keys are ignored.
* `Opt[T]`: the key is left out of the JSON when not given. `OptNull[T]`: absent stays absent, an explicit `null` stays `null`.
* Numbers are strict: `"5"` is not an integer, `5.0` is.
* `IsoDateTime` is an aware `datetime` in memory and `YYYY-MM-DDTHH:MM:SS.mmmZ` on the wire.
"""

import math
import re
import uuid as _uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Final, Literal, TypeVar, Union, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    SerializationInfo,
    StrictBool,
    StringConstraints,
    ValidationError,
    WrapValidator,
    create_model,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel
from pydantic_core import InitErrorDetails, PydanticCustomError

T = TypeVar('T')

JS_MAX_SAFE_INTEGER: Final = 2**53 - 1


# ── optional keys ───────────────────────────────────────────────────────────────────────────────
class _OptMarker:
    """Annotated metadata: this field is optional (the JSON key may be missing)."""

    __slots__ = ('nullable',)

    def __init__(self, nullable: bool) -> None:
        self.nullable = nullable

    def __repr__(self) -> str:
        return f'OptMarker(nullable={self.nullable})'


# `Opt`: None means "not given". `OptNull`: an explicit None is a real null and is kept.
Opt = Annotated[T | None, _OptMarker(False)]
OptNull = Annotated[T | None, _OptMarker(True)]

_OMIT_CACHE: dict[type, dict[str, tuple[str, bool]]] = {}


def _omittable(cls: type[BaseModel]) -> dict[str, tuple[str, bool]]:
    """name -> (alias, nullable) for the optional fields of `cls` (computed once per class)."""
    got = _OMIT_CACHE.get(cls)
    if got is None:
        got = {}
        for name, info in cls.model_fields.items():
            for meta in info.metadata:
                if isinstance(meta, _OptMarker):
                    got[name] = (info.serialization_alias or info.alias or name, meta.nullable)
        _OMIT_CACHE[cls] = got
    return got


class Model(BaseModel):
    """Base of every contract model. Serialise with `dump(model)` (JSON mode, camelCase)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @model_serializer(mode='wrap')
    def _omit_absent(self, handler: Any, info: SerializationInfo) -> dict[str, Any]:
        data = handler(self)
        for name, (alias, nullable) in _omittable(type(self)).items():
            key = alias if info.by_alias else name
            if key in data and data[key] is None and (not nullable or name not in self.model_fields_set):
                del data[key]
        return data

    def present_keys(self) -> set[str]:
        """Names of the fields a client really sent (for patches where every field is optional)."""
        omittable = _omittable(type(self))
        out: set[str] = set()
        for name in self.model_fields_set:
            if name not in type(self).model_fields:
                continue
            if getattr(self, name) is None and (name not in omittable or not omittable[name][1]):
                continue
            out.add(name)
        return out


def dump(model: BaseModel) -> dict[str, Any]:
    """The JSON object for this value: camelCase keys, absent optionals left out."""
    return model.model_dump(mode='json', by_alias=True)


def patch_keys(model: type[BaseModel]) -> list[str]:
    """JSON (camelCase) field names of a model: lets the gateway see which settings keys each owner takes."""
    return [info.alias or name for name, info in model.model_fields.items()]


def partial(model: type[Model], name: str, *, nullable: frozenset[str] = frozenset()) -> type[Model]:
    """A copy of `model` where every field is optional (`nullable` = names that also accept null)."""
    fields: dict[str, Any] = {}
    for fname, info in model.model_fields.items():
        inner: Any = Annotated[(info.annotation, *info.metadata)] if info.metadata else info.annotation
        marker = _OptMarker(fname in nullable)
        fields[fname] = (Annotated[inner | None, marker], None)
    aliases = {fname: (info.alias or fname) for fname, info in model.model_fields.items() if fname not in nullable}

    def reject_null(cls: Any, data: Any) -> Any:
        # Optional means "absent", not `null`: for patches a null must not pass as "not given".
        if isinstance(data, dict):
            for fname, alias in aliases.items():
                for key in (alias, fname):
                    if key in data and data[key] is None:
                        refine_fail(('Invalid input: expected value, received null', (key,)))
        return data

    return create_model(
        name, __base__=Model, __module__=model.__module__,
        __validators__={'_reject_null': model_validator(mode='before')(classmethod(reject_null))},
        **fields,
    )


# ── error reporting ─────────────────────────────────────────────────────────────────────────────
def error_message(err: Any) -> str:
    """The plain message for a pydantic error line (the wording the web app already shows)."""
    kind, ctx = err['type'], err.get('ctx') or {}
    if kind == 'missing':
        return 'Invalid input: expected value, received undefined'
    if kind == 'string_too_short':
        return f"Too small: expected string to have >={ctx['min_length']} characters"
    if kind == 'string_too_long':
        return f"Too big: expected string to have <={ctx['max_length']} characters"
    if kind == 'too_short':
        return f"Too small: expected array to have >={ctx['min_length']} items"
    if kind == 'too_long':
        return f"Too big: expected array to have <={ctx['max_length']} items"
    bounds = {
        'greater_than': ('Too small', '>', 'gt'), 'greater_than_equal': ('Too small', '>=', 'ge'),
        'less_than': ('Too big', '<', 'lt'), 'less_than_equal': ('Too big', '<=', 'le'),
    }
    if kind in bounds:
        word, op, key = bounds[kind]
        return f'{word}: expected number to be {op}{ctx[key]}'
    if kind == 'literal_error':
        return 'Invalid option: expected one of ' + '|'.join(f'"{x}"' for x in str(ctx.get('expected', '')).replace("'", '').split(' or '))
    if kind == 'bool_type':
        return 'Invalid input: expected boolean'
    if kind in ('string_type', 'str_type'):
        return 'Invalid input: expected string'
    if kind == 'model_attributes_type' or kind == 'dict_type':
        return 'Invalid input: expected object'
    if kind == 'list_type':
        return 'Invalid input: expected array'
    if kind == 'value_error':
        return str(err['msg']).removeprefix('Value error, ')
    return str(err['msg'])


def validation_details(exc: ValidationError) -> dict[str, str]:
    """`{path: message}` for a failed validation: dotted path (`lines.0.categoryId`), `_` for the root, the last message wins."""
    return {'.'.join(str(p) for p in e['loc']) or '_': error_message(e) for e in exc.errors(include_url=False)}


# ── refinements ─────────────────────────────────────────────────────────────────────────────────
def refine_fail(*issues: tuple[str, tuple[str | int, ...]] | str) -> None:
    """Raise one validation error with one line per issue: `'message'` (root) or `('message', ('path',))`. Keeps the paths a plain `ValueError` would lose."""
    lines: list[InitErrorDetails] = []
    for issue in issues:
        msg, loc = (issue, ()) if isinstance(issue, str) else issue
        lines.append(InitErrorDetails(type=PydanticCustomError('refine', msg), loc=tuple(loc), input=None))
    raise ValidationError.from_exception_data('refine', lines)


def discriminated(key: str, *models: type[Model]) -> Any:
    """Union picked by the `key` literal and validated against that member alone, so error paths read `schedule.day`, not `schedule.monthly.day`."""
    by_tag: dict[str, type[Model]] = {}
    for m in models:
        for tag in get_args(m.model_fields[key].annotation):
            by_tag[tag] = m
    expected = ' | '.join(f"'{t}'" for t in by_tag)

    def dispatch(value: Any, handler: Any) -> Any:
        if isinstance(value, models):
            return value
        tag = value.get(key) if isinstance(value, dict) else None
        member = by_tag.get(tag) if isinstance(tag, str) else None
        if member is None:
            if not isinstance(value, dict):
                raise PydanticCustomError(
                    'model_type', 'Invalid input: expected object, received {got}', {'got': _kind(value)}
                )
            refine_fail((f'Invalid discriminator value. Expected {expected}', (key,)))
        return member.model_validate(value)

    return Annotated[Union[models], Field(discriminator=key), WrapValidator(dispatch)]  # noqa: UP007


# ── scalar types ────────────────────────────────────────────────────────────────────────────────
_UUID_RE = re.compile(
    r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}'
    r'|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)'
)


def _uuid_check(v: Any) -> str:
    if isinstance(v, _uuid.UUID):
        v = str(v)
    if not isinstance(v, str):
        raise PydanticCustomError('uuid_type', 'Invalid input: expected string, received {got}', {'got': _kind(v)})
    if not _UUID_RE.fullmatch(v):
        raise PydanticCustomError('uuid', 'Invalid UUID')
    return v


def _kind(v: Any) -> str:
    return 'null' if v is None else type(v).__name__


Uuid = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, _uuid.UUID) else v), AfterValidator(_uuid_check)]


def _int_check(v: Any) -> int:
    """A real number with no fraction; not a string, not a boolean."""
    if isinstance(v, bool):
        raise PydanticCustomError('int_type', 'Invalid input: expected number, received boolean')
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, Decimal) and v == v.to_integral_value():
        return int(v)
    if isinstance(v, (int, float, Decimal)):
        raise PydanticCustomError('int_float', 'Invalid input: expected int, received float')
    raise PydanticCustomError('int_type', 'Invalid input: expected number, received {got}', {'got': _kind(v)})


Int = Annotated[int, BeforeValidator(_int_check)]
Paise = Annotated[int, BeforeValidator(_int_check), Field(ge=-JS_MAX_SAFE_INTEGER, le=JS_MAX_SAFE_INTEGER)]
PositivePaise = Annotated[int, BeforeValidator(_int_check), Field(gt=0, le=JS_MAX_SAFE_INTEGER)]
NonNegativePaise = Annotated[int, BeforeValidator(_int_check), Field(ge=0, le=JS_MAX_SAFE_INTEGER)]


def _number_check(v: Any) -> float:
    """Any finite number (ints included), nothing else."""
    if isinstance(v, bool) or not isinstance(v, (int, float, Decimal)):
        raise PydanticCustomError('number_type', 'Invalid input: expected number, received {got}', {'got': _kind(v)})
    f = float(v)
    if not math.isfinite(f):
        raise PydanticCustomError('number_finite', 'Invalid input: expected number, received NaN')
    return f


Number = Annotated[float, BeforeValidator(_number_check)]

Bool = StrictBool

_JS_NUMBER_RE = re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?', re.ASCII)


def _coerce_int(v: Any) -> int:
    """Integer from a query string: parsed as a number first, then checked for a fraction."""
    if isinstance(v, str):
        s = v.strip()
        if s == '':
            return 0
        if not _JS_NUMBER_RE.fullmatch(s):
            raise PydanticCustomError('int_type', 'Invalid input: expected number, received NaN')
        v = float(s)
    return _int_check(v)


CoerceInt = Annotated[int, BeforeValidator(_coerce_int)]

_TRUE_WORDS: Final = frozenset({'true', '1', 'yes', 'on', 'y', 'enabled'})
_FALSE_WORDS: Final = frozenset({'false', '0', 'no', 'off', 'n', 'disabled'})


def _string_bool(v: Any) -> bool:
    """A query-string boolean: the usual true/false words, case-insensitive."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        w = v.lower()
        if w in _TRUE_WORDS:
            return True
        if w in _FALSE_WORDS:
            return False
    raise PydanticCustomError('stringbool', 'Invalid input: expected boolean string')


StringBool = Annotated[bool, BeforeValidator(_string_bool)]


def regex_str(pattern: str, message: str, *, flags: int = re.ASCII) -> Any:
    """A string that must fully match `pattern`; a failure reads `message`."""
    rx = re.compile(pattern, flags)

    def check(v: str) -> str:
        if not rx.fullmatch(v):
            raise PydanticCustomError('string_pattern', message)
        return v

    return Annotated[str, AfterValidator(check)]


DateKey = regex_str(r'\d{4}-\d{2}-\d{2}', 'YYYY-MM-DD')
MonthKey = regex_str(r'\d{4}-(?:0[1-9]|1[0-2])', 'YYYY-MM')
TzName = Annotated[str, StringConstraints(min_length=1, max_length=64)]
SixDigits = regex_str(r'\d{6}', 'six digits')

_DATE_SRC = (
    r'(?:(?:\d\d[2468][048]|\d\d[13579][26]|\d\d0[48]|[02468][048]00|[13579][26]00)-02-29'
    r'|\d{4}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12]\d|3[01])|(?:0[469]|11)-(?:0[1-9]|[12]\d|30)|(?:02)-(?:0[1-9]|1\d|2[0-8])))'
)
_ISO_RE = re.compile(
    _DATE_SRC + r'T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)', re.ASCII
)


def iso_ms(d: datetime) -> str:
    """`Date.prototype.toISOString()`: UTC, exactly three fraction digits, `Z`."""
    u = d.astimezone(UTC)
    return f'{u:%Y-%m-%dT%H:%M:%S}.{u.microsecond // 1000:03d}Z'


def _parse_iso(v: Any) -> datetime:
    if isinstance(v, datetime):
        if v.tzinfo is None or v.utcoffset() is None:
            raise PydanticCustomError('datetime', 'Invalid ISO datetime: a time zone is required')
        return v.astimezone(UTC)
    if not isinstance(v, str):
        raise PydanticCustomError('datetime_type', 'Invalid input: expected string, received {got}', {'got': _kind(v)})
    if not _ISO_RE.fullmatch(v):
        raise PydanticCustomError('datetime', 'Invalid ISO datetime')
    return datetime.fromisoformat(v).astimezone(UTC)


IsoDateTime = Annotated[
    datetime, BeforeValidator(_parse_iso), PlainSerializer(iso_ms, return_type=str, when_used='json')
]


def _time_str(v: Any) -> Any:
    """For `z.string()` fields that hold a time: a `datetime` from the database becomes its ISO string."""
    return iso_ms(v) if isinstance(v, datetime) else v


TimeStr = Annotated[str, BeforeValidator(_time_str)]


# ── enums (same strings as TS; plain Literal so values compare and serialise as str) ─────────────
TxType = Literal['debit', 'credit']
TxSource = Literal['captured', 'recurring', 'manual', 'unaccounted']
TxStatus = Literal['pending', 'confirmed', 'reversed']

TX_TYPES: Final = get_args(TxType)
TX_SOURCES: Final = get_args(TxSource)
TX_STATUSES: Final = get_args(TxStatus)
