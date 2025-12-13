"""JSON backend selection for ZDS.

Uses orjson if available for 5-10x faster JSON parsing/serialization.
Falls back to standard json module otherwise.
"""

from typing import Any, Union

# Try orjson first (fastest)
try:
    import orjson
    
    def dumps(obj: Any) -> str:
        """Serialize object to JSON string."""
        return orjson.dumps(obj).decode("utf-8")
    
    def dumps_bytes(obj: Any) -> bytes:
        """Serialize object to JSON bytes."""
        return orjson.dumps(obj)
    
    def dumps_compact(obj: Any) -> str:
        """Serialize object to compact JSON string."""
        return orjson.dumps(obj).decode("utf-8")
    
    def loads(s: Union[str, bytes]) -> Any:
        """Parse JSON string or bytes."""
        return orjson.loads(s)
    
    BACKEND = "orjson"

except ImportError:
    # Try ujson (faster than stdlib)
    try:
        import ujson
        
        def dumps(obj: Any) -> str:
            return ujson.dumps(obj, ensure_ascii=False)
        
        def dumps_bytes(obj: Any) -> bytes:
            return ujson.dumps(obj, ensure_ascii=False).encode("utf-8")
        
        def dumps_compact(obj: Any) -> str:
            return ujson.dumps(obj, ensure_ascii=False)
        
        def loads(s: Union[str, bytes]) -> Any:
            if isinstance(s, bytes):
                s = s.decode("utf-8")
            return ujson.loads(s)
        
        BACKEND = "ujson"
    
    except ImportError:
        # Fall back to stdlib json
        import json as _json
        
        def dumps(obj: Any) -> str:
            return _json.dumps(obj, ensure_ascii=False)
        
        def dumps_bytes(obj: Any) -> bytes:
            return _json.dumps(obj, ensure_ascii=False).encode("utf-8")
        
        def dumps_compact(obj: Any) -> str:
            return _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        
        def loads(s: Union[str, bytes]) -> Any:
            if isinstance(s, bytes):
                s = s.decode("utf-8")
            return _json.loads(s)
        
        BACKEND = "json"


def get_backend() -> str:
    """Return the active JSON backend name."""
    return BACKEND
