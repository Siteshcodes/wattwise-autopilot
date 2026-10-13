"""Hashes contain canonical business data, not IDs, durations, or solver timings."""
import hashlib
import json
from decimal import Decimal

from .schema import Request, Schedule


def _canonical(value):
    if isinstance(value,dict):
        return {k:_canonical(v) for k,v in sorted(value.items())}
    if isinstance(value,list):
        return [_canonical(v) for v in value]
    if isinstance(value,bool) or value is None:
        return value
    if isinstance(value,(float,int,Decimal)):
        number=Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Non-finite business number cannot be hashed")
        return format(number.normalize(),'f') if number else "0"
    return value


def digest(data):
    payload=json.dumps(_canonical(data),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def business_input(request: Request):
    body=request.model_dump(mode="json")
    body.pop("request_id")
    body["negotiable"]=sorted(body["negotiable"])
    return body


def schedule_hash(schedule: Schedule):
    return digest(schedule.model_dump(mode="json"))
