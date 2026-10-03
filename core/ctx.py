import contextvars

tenant_id = contextvars.ContextVar("tenant_id", default=None)
request_id = contextvars.ContextVar("request_id", default="")
